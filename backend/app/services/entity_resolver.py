"""Entity resolution service using fuzzy matching and AI."""
import asyncio
import re
import sys
import traceback
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from openai import AsyncOpenAI
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.entity import (
    Entity, EntityBatch, EntityResolution, EntityType, ResolutionStatus, BatchStatus
)
from app.services.charity_commission import CharityCommissionService
import structlog

logger = structlog.get_logger()


def debug_log(msg: str, batch_id: str = "", entity_name: str = "", level: str = "DEBUG"):
    """Log debug messages to stdout/stderr for Railway visibility."""
    timestamp = datetime.utcnow().isoformat()
    context = ""
    if batch_id:
        context += f"[batch={batch_id}] "
    if entity_name:
        context += f"[entity='{entity_name[:30]}...'] " if len(entity_name) > 30 else f"[entity='{entity_name}'] "
    formatted = f"[{level}] [{timestamp}] {context}{msg}"
    print(formatted, file=sys.stdout, flush=True)


class EntityResolverService:
    """Service for resolving entities to Charity Commission records."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.charity_service = CharityCommissionService()
        self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
    
    async def close(self):
        """Clean up resources."""
        await self.charity_service.close()
    
    @staticmethod
    def normalize_name(name: str) -> str:
        """Normalize entity name for comparison."""
        # Convert to lowercase
        normalized = name.lower()
        # Remove common suffixes
        suffixes = [
            " limited", " ltd", " plc", " llp", " cic", " cio",
            " charity", " charitable", " trust", " foundation",
            " association", " society", " organisation", " organization",
            " uk", " england", " wales", " scotland",
        ]
        for suffix in suffixes:
            normalized = normalized.replace(suffix, "")
        # Remove special characters
        normalized = re.sub(r'[^\w\s]', '', normalized)
        # Remove extra whitespace
        normalized = ' '.join(normalized.split())
        return normalized.strip()
    
    @staticmethod
    def calculate_similarity(name1: str, name2: str) -> float:
        """Calculate similarity score between two names."""
        norm1 = EntityResolverService.normalize_name(name1)
        norm2 = EntityResolverService.normalize_name(name2)
        return SequenceMatcher(None, norm1, norm2).ratio()
    
    async def search_candidates(
        self,
        entity_name: str,
        max_results: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Search for matching charity candidates.
        
        Args:
            entity_name: Entity name to search
            max_results: Maximum number of candidates
        
        Returns:
            List of candidate matches with scores
        """
        candidates = []
        
        try:
            # Search Charity Commission
            results = await self.charity_service.search_charities(
                entity_name,
                page_size=max_results * 2,  # Get extra for filtering
            )
            
            charities = results.get("charities", results) if isinstance(results, dict) else results
            if not isinstance(charities, list):
                charities = []
            
            for charity in charities[:max_results]:
                charity_name = charity.get("charityName") or charity.get("name", "")
                charity_number = charity.get("charityNumber") or charity.get("registeredCharityNumber", "")
                
                similarity = self.calculate_similarity(entity_name, charity_name)
                
                candidates.append({
                    "charity_number": charity_number,
                    "name": charity_name,
                    "status": charity.get("registrationStatus"),
                    "similarity_score": similarity,
                    "raw_data": charity,
                })
            
            # Sort by similarity
            candidates.sort(key=lambda x: x["similarity_score"], reverse=True)
            
        except Exception as e:
            logger.error("Error searching candidates", entity_name=entity_name, error=str(e))
        
        return candidates[:max_results]
    
    async def ai_resolve_entity(
        self,
        entity_name: str,
        candidates: List[Dict[str, Any]],
        original_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[Tuple[str, float, str]]:
        """
        Use AI to select the best matching candidate.
        
        Args:
            entity_name: Original entity name
            candidates: List of candidate matches
            original_data: Additional context from original upload
        
        Returns:
            Tuple of (charity_number, confidence, reasoning) or None
        """
        if not self.openai_client or not candidates:
            return None
        
        # Prepare context
        context = f"Original entity name: {entity_name}\n"
        if original_data:
            context += f"Additional context: {original_data}\n"
        
        context += "\nCandidate matches:\n"
        for i, candidate in enumerate(candidates, 1):
            context += f"{i}. {candidate['name']} (Charity #{candidate['charity_number']}, "
            context += f"Status: {candidate.get('status', 'Unknown')}, "
            context += f"Similarity: {candidate['similarity_score']:.2%})\n"
        
        prompt = f"""You are an expert at matching organization names to official charity records.

{context}

Task: Determine if any of these candidates is a match for the original entity.

Respond in JSON format:
{{
    "match_found": true/false,
    "selected_index": <1-based index of best match, or null>,
    "confidence": <0.0 to 1.0>,
    "reasoning": "<brief explanation>"
}}

Consider:
- Name variations (abbreviations, spelling differences)
- Common organizational suffixes (Ltd, Charity, Foundation)
- Registration status
- Similarity scores

Be conservative - only match if confident it's the same organization."""

        try:
            response = await self.openai_client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are a charity data matching expert."},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
            )
            
            import json
            result = json.loads(response.choices[0].message.content)
            
            if result.get("match_found") and result.get("selected_index"):
                idx = result["selected_index"] - 1
                if 0 <= idx < len(candidates):
                    return (
                        candidates[idx]["charity_number"],
                        result.get("confidence", 0.8),
                        result.get("reasoning", "AI matched"),
                    )
            
            return None
            
        except Exception as e:
            logger.error("AI resolution error", error=str(e))
            return None
    
    async def resolve_entity(
        self,
        entity: Entity,
        use_ai: bool = True,
    ) -> Entity:
        """
        Resolve a single entity to Charity Commission records.
        
        Args:
            entity: Entity to resolve
            use_ai: Whether to use AI for matching
        
        Returns:
            Updated entity
        """
        entity_name = entity.original_name
        batch_id = str(entity.batch_id) if entity.batch_id else ""
        
        debug_log("Starting resolution", batch_id=batch_id, entity_name=entity_name)
        
        # First, check if entity already has a charity number
        if entity.charity_number:
            debug_log(f"Entity has existing charity_number={entity.charity_number}, attempting direct lookup", 
                     batch_id=batch_id, entity_name=entity_name)
            charity_data = await self.charity_service.get_full_charity_details(entity.charity_number)
            if charity_data:
                debug_log(f"Direct lookup SUCCESS", batch_id=batch_id, entity_name=entity_name)
                parsed = CharityCommissionService.parse_charity_data(charity_data)
                await self._update_entity_from_charity(entity, parsed, "direct_lookup", 1.0)
                return entity
            else:
                debug_log(f"Direct lookup returned no data", batch_id=batch_id, entity_name=entity_name)
        
        # Try to extract charity number from name or original data
        debug_log("Attempting to extract charity number from name/data", batch_id=batch_id, entity_name=entity_name)
        extracted_number = CharityCommissionService.extract_charity_number(entity.original_name)
        if not extracted_number and entity.original_data:
            for key, value in entity.original_data.items():
                if isinstance(value, str):
                    extracted_number = CharityCommissionService.extract_charity_number(value)
                    if extracted_number:
                        debug_log(f"Found charity number in original_data['{key}']: {extracted_number}", 
                                 batch_id=batch_id, entity_name=entity_name)
                        break
        
        if extracted_number:
            debug_log(f"Extracted charity number: {extracted_number}, fetching details", 
                     batch_id=batch_id, entity_name=entity_name)
            charity_data = await self.charity_service.get_full_charity_details(extracted_number)
            if charity_data:
                debug_log(f"Number extraction lookup SUCCESS", batch_id=batch_id, entity_name=entity_name)
                parsed = CharityCommissionService.parse_charity_data(charity_data)
                await self._update_entity_from_charity(entity, parsed, "number_extraction", 0.95)
                return entity
            else:
                debug_log(f"Number extraction lookup returned no data", batch_id=batch_id, entity_name=entity_name)
        
        # Search for candidates by name
        debug_log("Searching for candidates by name", batch_id=batch_id, entity_name=entity_name)
        candidates = await self.search_candidates(entity.original_name)
        
        if not candidates:
            debug_log("No candidates found - marking as NO_MATCH", batch_id=batch_id, entity_name=entity_name)
            entity.resolution_status = ResolutionStatus.NO_MATCH
            entity.resolved_at = datetime.utcnow()
            await self.db.flush()
            return entity
        
        debug_log(f"Found {len(candidates)} candidates", batch_id=batch_id, entity_name=entity_name)
        for i, c in enumerate(candidates[:3]):  # Log top 3
            debug_log(f"  Candidate {i+1}: '{c['name']}' (#{c['charity_number']}) - similarity={c['similarity_score']:.3f}", 
                     batch_id=batch_id, entity_name=entity_name)
        
        # Save all candidates as resolutions
        for candidate in candidates:
            resolution = EntityResolution(
                entity_id=entity.id,
                charity_number=candidate["charity_number"],
                candidate_name=candidate["name"],
                candidate_data=candidate.get("raw_data"),
                confidence_score=candidate["similarity_score"],
                match_method="fuzzy_search",
            )
            self.db.add(resolution)
        
        # Check for exact match (high similarity)
        best_match = candidates[0]
        if best_match["similarity_score"] >= 0.95:
            debug_log(f"High confidence match (score={best_match['similarity_score']:.3f} >= 0.95), fetching details", 
                     batch_id=batch_id, entity_name=entity_name)
            charity_data = await self.charity_service.get_full_charity_details(best_match["charity_number"])
            if charity_data:
                debug_log(f"Exact match SUCCESS: '{best_match['name']}'", batch_id=batch_id, entity_name=entity_name)
                parsed = CharityCommissionService.parse_charity_data(charity_data)
                await self._update_entity_from_charity(
                    entity, parsed, "exact_match", best_match["similarity_score"]
                )
                # Mark the resolution as selected
                await self.db.flush()
                await self.db.execute(
                    update(EntityResolution)
                    .where(EntityResolution.entity_id == entity.id)
                    .where(EntityResolution.charity_number == best_match["charity_number"])
                    .values(is_selected=True)
                )
                return entity
            else:
                debug_log(f"Exact match lookup returned no data", batch_id=batch_id, entity_name=entity_name)
        
        # Try AI matching if enabled and we have multiple candidates
        if use_ai and self.openai_client:
            debug_log("Attempting AI matching (OpenAI configured)", batch_id=batch_id, entity_name=entity_name)
            ai_result = await self.ai_resolve_entity(
                entity.original_name,
                candidates,
                entity.original_data,
            )
            
            if ai_result:
                charity_number, confidence, reasoning = ai_result
                debug_log(f"AI matched to #{charity_number} with confidence={confidence:.2f}: {reasoning[:50]}...", 
                         batch_id=batch_id, entity_name=entity_name)
                charity_data = await self.charity_service.get_full_charity_details(charity_number)
                if charity_data:
                    debug_log(f"AI match lookup SUCCESS", batch_id=batch_id, entity_name=entity_name)
                    parsed = CharityCommissionService.parse_charity_data(charity_data)
                    await self._update_entity_from_charity(entity, parsed, "ai_match", confidence)
                    entity.enriched_data = entity.enriched_data or {}
                    entity.enriched_data["ai_reasoning"] = reasoning
                    
                    # Mark the resolution as selected
                    await self.db.flush()
                    await self.db.execute(
                        update(EntityResolution)
                        .where(EntityResolution.entity_id == entity.id)
                        .where(EntityResolution.charity_number == charity_number)
                        .values(is_selected=True)
                    )
                    return entity
            else:
                debug_log("AI matching did not produce a result", batch_id=batch_id, entity_name=entity_name)
        elif use_ai:
            debug_log("AI matching requested but OpenAI not configured (no API key)", batch_id=batch_id, entity_name=entity_name)
        
        # Multiple candidates, needs manual review
        # Store the best match's confidence so user knows how close we got
        best_candidate_score = candidates[0]["similarity_score"] if candidates else None
        
        if len(candidates) > 1:
            debug_log(f"Multiple candidates ({len(candidates)}), no confident match - marking MULTIPLE_MATCHES", 
                     batch_id=batch_id, entity_name=entity_name)
            entity.resolution_status = ResolutionStatus.MULTIPLE_MATCHES
        else:
            debug_log(f"Single candidate but not confident enough - marking MANUAL_REVIEW", 
                     batch_id=batch_id, entity_name=entity_name)
            entity.resolution_status = ResolutionStatus.MANUAL_REVIEW
        
        # Store the best candidate's confidence score for user reference
        entity.resolution_confidence = best_candidate_score
        entity.resolution_method = "needs_review"
        entity.resolved_at = datetime.utcnow()
        await self.db.flush()
        debug_log(f"Resolution complete: status={entity.resolution_status}", batch_id=batch_id, entity_name=entity_name)
        return entity
    
    async def _update_entity_from_charity(
        self,
        entity: Entity,
        charity_data: Dict[str, Any],
        method: str,
        confidence: float,
    ):
        """Update entity with charity data."""
        entity.entity_type = EntityType.CHARITY
        entity.resolved_name = charity_data.get("name")
        entity.charity_number = charity_data.get("charity_number")
        entity.charity_status = charity_data.get("status")
        entity.charity_registration_date = charity_data.get("registration_date")
        entity.charity_removal_date = charity_data.get("removal_date")
        entity.charity_activities = charity_data.get("activities")
        entity.charity_contact_email = charity_data.get("contact_email")
        entity.charity_contact_phone = charity_data.get("contact_phone")
        entity.charity_website = charity_data.get("website")
        entity.charity_address = charity_data.get("address")
        entity.latest_income = charity_data.get("latest_income")
        entity.latest_expenditure = charity_data.get("latest_expenditure")
        entity.latest_financial_year_end = charity_data.get("financial_year_end")
        entity.resolution_status = ResolutionStatus.MATCHED
        entity.resolution_confidence = confidence
        entity.resolution_method = method
        entity.resolved_at = datetime.utcnow()
        
        # Store additional data
        entity.enriched_data = entity.enriched_data or {}
        entity.enriched_data["trustees"] = charity_data.get("trustees", [])
        entity.enriched_data["subsidiaries"] = charity_data.get("subsidiaries", [])
        
        await self.db.flush()
    
    async def process_batch(
        self,
        batch_id: UUID,
        use_ai: bool = True,
        max_concurrent: int = 5,
    ) -> EntityBatch:
        """
        Process all entities in a batch.
        
        Args:
            batch_id: Batch ID to process
            use_ai: Whether to use AI for matching
            max_concurrent: Maximum concurrent resolutions
        
        Returns:
            Updated batch
        """
        batch_id_str = str(batch_id)
        start_time = datetime.utcnow()
        
        debug_log("=== EntityResolver.process_batch STARTED ===", batch_id=batch_id_str)
        debug_log(f"Parameters: use_ai={use_ai}, max_concurrent={max_concurrent}", batch_id=batch_id_str)
        
        # Get batch
        result = await self.db.execute(
            select(EntityBatch).where(EntityBatch.id == batch_id)
        )
        batch = result.scalar_one_or_none()
        
        if not batch:
            debug_log(f"Batch not found!", batch_id=batch_id_str, level="ERROR")
            raise ValueError(f"Batch {batch_id} not found")
        
        debug_log(f"Found batch: name='{batch.name}', current_status={batch.status}, user_id={batch.user_id}", batch_id=batch_id_str)
        
        # Update batch status
        batch.status = BatchStatus.PROCESSING
        batch.processing_started_at = datetime.utcnow()
        await self.db.flush()
        debug_log("Updated batch status to PROCESSING", batch_id=batch_id_str)
        
        try:
            # Get all entities in batch (both pending and those needing review)
            result = await self.db.execute(
                select(Entity)
                .where(Entity.batch_id == batch_id)
                .where(Entity.resolution_status.in_([
                    ResolutionStatus.PENDING,
                    ResolutionStatus.MANUAL_REVIEW,
                    ResolutionStatus.MULTIPLE_MATCHES,
                ]))
            )
            entities = result.scalars().all()
            
            debug_log(f"Found {len(entities)} entities to process (PENDING/MANUAL_REVIEW/MULTIPLE_MATCHES)", batch_id=batch_id_str)
            
            if len(entities) == 0:
                debug_log("No entities to process, marking batch as completed", batch_id=batch_id_str, level="INFO")
                batch.status = BatchStatus.COMPLETED
                batch.processing_completed_at = datetime.utcnow()
                await self.db.flush()
                return batch
            
            # Log entity names for debugging
            entity_names = [e.original_name for e in entities[:10]]  # First 10
            debug_log(f"First entities to process: {entity_names}", batch_id=batch_id_str)
            
            # Get total count of all entities (not just pending)
            total_result = await self.db.execute(
                select(Entity).where(Entity.batch_id == batch_id)
            )
            all_entities = total_result.scalars().all()
            batch.total_records = len(all_entities)
            
            # Count already matched entities
            already_matched = sum(1 for e in all_entities if e.resolution_status == ResolutionStatus.MATCHED)
            debug_log(f"Total entities in batch: {len(all_entities)}, already matched: {already_matched}", batch_id=batch_id_str)
            
            processed = 0
            matched = already_matched
            failed = 0
            
            debug_log("Starting SEQUENTIAL processing (one entity at a time)", batch_id=batch_id_str)
            
            for entity in entities:
                entity_start = datetime.utcnow()
                try:
                    debug_log(f"Processing entity {processed + 1}/{len(entities)}", 
                             batch_id=batch_id_str, entity_name=entity.original_name)
                    
                    # Log original data for debugging
                    if entity.original_data:
                        debug_log(f"Original data keys: {list(entity.original_data.keys())}", 
                                 batch_id=batch_id_str, entity_name=entity.original_name)
                    
                    await self.resolve_entity(entity, use_ai=use_ai)
                    
                    entity_duration = (datetime.utcnow() - entity_start).total_seconds()
                    
                    if entity.resolution_status == ResolutionStatus.MATCHED:
                        matched += 1
                        debug_log(f"✓ MATCHED in {entity_duration:.2f}s: resolved_name='{entity.resolved_name}', charity_number={entity.charity_number}, method={entity.resolution_method}, confidence={entity.resolution_confidence}", 
                                 batch_id=batch_id_str, entity_name=entity.original_name, level="INFO")
                    elif entity.resolution_status == ResolutionStatus.NO_MATCH:
                        debug_log(f"✗ NO_MATCH in {entity_duration:.2f}s: No matching charity found", 
                                 batch_id=batch_id_str, entity_name=entity.original_name)
                    elif entity.resolution_status == ResolutionStatus.MULTIPLE_MATCHES:
                        debug_log(f"? MULTIPLE_MATCHES in {entity_duration:.2f}s: Multiple candidates found, needs review", 
                                 batch_id=batch_id_str, entity_name=entity.original_name)
                    else:
                        debug_log(f"- Status={entity.resolution_status} in {entity_duration:.2f}s", 
                                 batch_id=batch_id_str, entity_name=entity.original_name)
                                 
                except Exception as e:
                    entity_duration = (datetime.utcnow() - entity_start).total_seconds()
                    error_tb = traceback.format_exc()
                    debug_log(f"✗ ERROR in {entity_duration:.2f}s: {type(e).__name__}: {str(e)}", 
                             batch_id=batch_id_str, entity_name=entity.original_name, level="ERROR")
                    debug_log(f"Traceback:\n{error_tb}", batch_id=batch_id_str, level="ERROR")
                    
                    logger.error("Entity resolution error", 
                                entity_id=str(entity.id), 
                                entity_name=entity.original_name,
                                error=str(e),
                                error_type=type(e).__name__)
                    entity.resolution_status = ResolutionStatus.MANUAL_REVIEW
                    entity.resolved_at = datetime.utcnow()
                    failed += 1
                    
                finally:
                    processed += 1
                    batch.processed_records = already_matched + processed
                    batch.matched_records = matched
                    batch.failed_records = failed
                    
                    # Flush after each entity to save progress
                    await self.db.flush()
                    
                    # Log progress every 10 entities or on each entity in small batches
                    if processed % 10 == 0 or len(entities) <= 20:
                        elapsed = (datetime.utcnow() - start_time).total_seconds()
                        rate = processed / elapsed if elapsed > 0 else 0
                        debug_log(f"=== PROGRESS: {processed}/{len(entities)} ({(processed/len(entities)*100):.1f}%) | matched={matched} | failed={failed} | rate={rate:.2f}/sec ===", 
                                 batch_id=batch_id_str, level="INFO")
            
            total_duration = (datetime.utcnow() - start_time).total_seconds()
            debug_log(f"=== ALL ENTITIES PROCESSED in {total_duration:.2f}s ===", batch_id=batch_id_str, level="INFO")
            debug_log(f"Final counts: total={processed}, matched={matched}, failed={failed}", batch_id=batch_id_str, level="INFO")
            
            # Update batch status
            if failed > 0 and matched == 0:
                batch.status = BatchStatus.FAILED
                debug_log("Setting batch status to FAILED (all entities failed)", batch_id=batch_id_str, level="ERROR")
            elif failed > 0:
                batch.status = BatchStatus.PARTIAL
                debug_log("Setting batch status to PARTIAL (some entities failed)", batch_id=batch_id_str)
            else:
                batch.status = BatchStatus.COMPLETED
                debug_log("Setting batch status to COMPLETED (all successful)", batch_id=batch_id_str, level="INFO")
            
            batch.processing_completed_at = datetime.utcnow()
            await self.db.flush()
            
            debug_log(f"=== EntityResolver.process_batch FINISHED ===", batch_id=batch_id_str, level="INFO")
            debug_log(f"Final status: {batch.status}, total_records={batch.total_records}, processed={batch.processed_records}, matched={batch.matched_records}, failed={batch.failed_records}", 
                     batch_id=batch_id_str, level="INFO")
            
        except Exception as e:
            total_duration = (datetime.utcnow() - start_time).total_seconds()
            error_tb = traceback.format_exc()
            debug_log(f"=== EXCEPTION in process_batch after {total_duration:.2f}s ===", batch_id=batch_id_str, level="ERROR")
            debug_log(f"Exception: {type(e).__name__}: {str(e)}", batch_id=batch_id_str, level="ERROR")
            debug_log(f"Traceback:\n{error_tb}", batch_id=batch_id_str, level="ERROR")
            
            batch.status = BatchStatus.FAILED
            batch.error_message = f"{type(e).__name__}: {str(e)}"
            await self.db.flush()
            raise
        
        finally:
            debug_log("Closing charity service connection", batch_id=batch_id_str)
            await self.close()
        
        return batch
    
    async def confirm_resolution(
        self,
        entity_id: UUID,
        resolution_id: Optional[UUID] = None,
        charity_number: Optional[str] = None,
    ) -> Entity:
        """
        Confirm or manually set entity resolution.
        
        Args:
            entity_id: Entity to update
            resolution_id: Resolution to confirm (if from candidates)
            charity_number: Manual charity number entry
        
        Returns:
            Updated entity
        """
        result = await self.db.execute(select(Entity).where(Entity.id == entity_id))
        entity = result.scalar_one_or_none()
        
        if not entity:
            raise ValueError(f"Entity {entity_id} not found")
        
        charity_num = charity_number
        
        # If resolution_id provided, get the charity number from it
        if resolution_id:
            res_result = await self.db.execute(
                select(EntityResolution).where(EntityResolution.id == resolution_id)
            )
            resolution = res_result.scalar_one_or_none()
            if resolution:
                charity_num = resolution.charity_number
                # Mark as selected
                resolution.is_selected = True
                await self.db.flush()
        
        if charity_num:
            # Fetch full charity details
            charity_data = await self.charity_service.get_full_charity_details(charity_num)
            if charity_data:
                parsed = CharityCommissionService.parse_charity_data(charity_data)
                await self._update_entity_from_charity(entity, parsed, "manual_confirm", 1.0)
                entity.resolution_status = ResolutionStatus.CONFIRMED
        else:
            # Mark as rejected/no match
            entity.resolution_status = ResolutionStatus.REJECTED
            entity.resolved_at = datetime.utcnow()
        
        await self.db.flush()
        await self.close()
        return entity
