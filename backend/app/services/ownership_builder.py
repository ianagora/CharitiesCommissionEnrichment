"""Recursive ownership tree builder service."""
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entity import Entity, EntityOwnership, EntityType
from app.services.charity_commission import CharityCommissionService
import structlog

logger = structlog.get_logger()


class OwnershipTreeBuilder:
    """Service for building recursive corporate ownership trees."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.charity_service = CharityCommissionService()
        self._visited_charities: Set[str] = set()
        self._visited_companies: Set[str] = set()
    
    async def close(self):
        """Clean up resources."""
        await self.charity_service.close()
    
    async def build_tree_for_entity(
        self,
        entity_id: UUID,
        max_depth: int = 3,
        direction: str = "both",  # "up", "down", "both"
    ) -> Dict[str, Any]:
        """
        Build ownership tree for an entity.
        
        Args:
            entity_id: Root entity ID
            max_depth: Maximum levels to traverse
            direction: Direction to build tree
        
        Returns:
            Tree structure with entities and relationships
        """
        result = await self.db.execute(select(Entity).where(Entity.id == entity_id))
        root_entity = result.scalar_one_or_none()
        
        if not root_entity:
            raise ValueError(f"Entity {entity_id} not found")
        
        tree = {
            "root": await self._entity_to_dict(root_entity),
            "children": [],
            "parents": [],
            "total_entities": 1,
            "max_depth_reached": 0,
        }
        
        # Reset visited sets
        self._visited_charities = set()
        self._visited_companies = set()
        
        if root_entity.charity_number:
            self._visited_charities.add(root_entity.charity_number)
        if root_entity.company_number:
            self._visited_companies.add(root_entity.company_number)
        
        # Build downward tree (subsidiaries)
        if direction in ("down", "both") and root_entity.charity_number:
            children, depth = await self._build_downward_tree(
                root_entity,
                current_depth=1,
                max_depth=max_depth,
            )
            tree["children"] = children
            tree["max_depth_reached"] = max(tree["max_depth_reached"], depth)
            tree["total_entities"] += self._count_tree_entities(children)
        
        # Build upward tree (parent organizations)
        if direction in ("up", "both"):
            parents, depth = await self._build_upward_tree(
                root_entity,
                current_depth=1,
                max_depth=max_depth,
            )
            tree["parents"] = parents
            tree["max_depth_reached"] = max(tree["max_depth_reached"], depth)
            tree["total_entities"] += self._count_tree_entities(parents)
        
        await self.close()
        return tree
    
    async def _build_downward_tree(
        self,
        parent_entity: Entity,
        current_depth: int,
        max_depth: int,
    ) -> tuple[List[Dict[str, Any]], int]:
        """Build tree of subsidiaries and related entities."""
        if current_depth > max_depth:
            return [], current_depth - 1
        
        children = []
        max_depth_reached = current_depth
        
        # Get subsidiaries from Charity Commission
        if parent_entity.charity_number:
            try:
                subsidiaries = await self.charity_service.get_charity_subsidiaries(
                    parent_entity.charity_number
                )
                
                for sub in subsidiaries:
                    sub_name = sub.get("subsidiaryName", "Unknown")
                    company_number = sub.get("companyNumber")
                    
                    # Skip if already visited
                    if company_number and company_number in self._visited_companies:
                        continue
                    if company_number:
                        self._visited_companies.add(company_number)
                    
                    # Create or find child entity
                    child_entity = await self._get_or_create_subsidiary_entity(
                        parent_entity,
                        sub_name,
                        company_number,
                        current_depth,
                    )
                    
                    if child_entity:
                        # Create ownership relationship
                        await self._create_ownership(
                            owner_id=parent_entity.id,
                            owned_id=child_entity.id,
                            ownership_type="subsidiary",
                            source="charity_commission",
                        )
                        
                        child_dict = await self._entity_to_dict(child_entity)
                        child_dict["ownership_type"] = "subsidiary"
                        
                        # Recursively build children's tree
                        if child_entity.charity_number:
                            grandchildren, depth = await self._build_downward_tree(
                                child_entity,
                                current_depth + 1,
                                max_depth,
                            )
                            child_dict["children"] = grandchildren
                            max_depth_reached = max(max_depth_reached, depth)
                        else:
                            child_dict["children"] = []
                        
                        children.append(child_dict)
                
            except Exception as e:
                logger.error(
                    "Error getting subsidiaries",
                    charity_number=parent_entity.charity_number,
                    error=str(e),
                )
        
        # Also check trustees and related charities from enriched data
        if parent_entity.enriched_data:
            trustees = parent_entity.enriched_data.get("trustees", [])
            for trustee in trustees:
                trustee_name = trustee.get("name", "")
                
                # Check if trustee is also a charity
                try:
                    search_results = await self.charity_service.search_charities(
                        trustee_name, page_size=3
                    )
                    charities = search_results.get("charities", [])
                    
                    for charity in charities:
                        charity_num = charity.get("charityNumber") or charity.get("registeredCharityNumber")
                        if not charity_num or charity_num in self._visited_charities:
                            continue
                        if charity_num == parent_entity.charity_number:
                            continue
                        
                        # Check name similarity
                        charity_name = charity.get("charityName") or charity.get("name", "")
                        if charity_name.lower() == trustee_name.lower():
                            self._visited_charities.add(charity_num)
                            
                            # Create related entity
                            related_entity = await self._get_or_create_related_charity(
                                parent_entity,
                                charity_num,
                                charity_name,
                                current_depth,
                            )
                            
                            if related_entity:
                                await self._create_ownership(
                                    owner_id=parent_entity.id,
                                    owned_id=related_entity.id,
                                    ownership_type="trustee_charity",
                                    source="charity_commission",
                                    description=f"Trustee: {trustee_name}",
                                )
                                
                                child_dict = await self._entity_to_dict(related_entity)
                                child_dict["ownership_type"] = "trustee_charity"
                                child_dict["children"] = []
                                children.append(child_dict)
                            break
                            
                except Exception as e:
                    logger.warning("Error checking trustee charity", trustee=trustee_name, error=str(e))
        
        return children, max_depth_reached
    
    async def _build_upward_tree(
        self,
        child_entity: Entity,
        current_depth: int,
        max_depth: int,
    ) -> tuple[List[Dict[str, Any]], int]:
        """Build tree of parent organizations."""
        if current_depth > max_depth:
            return [], current_depth - 1
        
        parents = []
        max_depth_reached = current_depth
        
        # Check existing parent relationships in database
        result = await self.db.execute(
            select(EntityOwnership)
            .where(EntityOwnership.owned_id == child_entity.id)
        )
        existing_ownerships = result.scalars().all()
        
        for ownership in existing_ownerships:
            owner_result = await self.db.execute(
                select(Entity).where(Entity.id == ownership.owner_id)
            )
            owner = owner_result.scalar_one_or_none()
            
            if owner:
                if owner.charity_number and owner.charity_number in self._visited_charities:
                    continue
                if owner.charity_number:
                    self._visited_charities.add(owner.charity_number)
                
                parent_dict = await self._entity_to_dict(owner)
                parent_dict["ownership_type"] = ownership.ownership_type
                
                # Recursively build parent's tree
                grandparents, depth = await self._build_upward_tree(
                    owner,
                    current_depth + 1,
                    max_depth,
                )
                parent_dict["parents"] = grandparents
                max_depth_reached = max(max_depth_reached, depth)
                
                parents.append(parent_dict)
        
        return parents, max_depth_reached
    
    async def _get_or_create_subsidiary_entity(
        self,
        parent_entity: Entity,
        name: str,
        company_number: Optional[str],
        level: int,
    ) -> Optional[Entity]:
        """Get or create an entity for a subsidiary."""
        # Check if entity already exists
        if company_number:
            result = await self.db.execute(
                select(Entity)
                .where(Entity.batch_id == parent_entity.batch_id)
                .where(Entity.company_number == company_number)
            )
            existing = result.scalar_one_or_none()
            if existing:
                return existing
        
        # Create new entity
        entity = Entity(
            batch_id=parent_entity.batch_id,
            original_name=name,
            entity_type=EntityType.COMPANY,
            resolved_name=name,
            company_number=company_number,
            parent_entity_id=parent_entity.id,
            ownership_level=level,
            resolution_status="matched",
            resolution_confidence=1.0,
            resolution_method="subsidiary_discovery",
        )
        self.db.add(entity)
        await self.db.flush()
        await self.db.refresh(entity)
        return entity
    
    async def _get_or_create_related_charity(
        self,
        parent_entity: Entity,
        charity_number: str,
        name: str,
        level: int,
    ) -> Optional[Entity]:
        """Get or create an entity for a related charity."""
        # Check if entity already exists
        result = await self.db.execute(
            select(Entity)
            .where(Entity.batch_id == parent_entity.batch_id)
            .where(Entity.charity_number == charity_number)
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing
        
        # Fetch charity data
        charity_data = await self.charity_service.get_full_charity_details(charity_number)
        
        if not charity_data:
            return None
        
        parsed = CharityCommissionService.parse_charity_data(charity_data)
        
        # Create new entity
        entity = Entity(
            batch_id=parent_entity.batch_id,
            original_name=name,
            entity_type=EntityType.CHARITY,
            resolved_name=parsed.get("name"),
            charity_number=charity_number,
            charity_status=parsed.get("status"),
            charity_registration_date=parsed.get("registration_date"),
            charity_activities=parsed.get("activities"),
            charity_contact_email=parsed.get("contact_email"),
            charity_website=parsed.get("website"),
            charity_address=parsed.get("address"),
            latest_income=parsed.get("latest_income"),
            latest_expenditure=parsed.get("latest_expenditure"),
            latest_financial_year_end=parsed.get("financial_year_end"),
            parent_entity_id=parent_entity.id,
            ownership_level=level,
            resolution_status="matched",
            resolution_confidence=1.0,
            resolution_method="related_discovery",
            enriched_data={
                "trustees": parsed.get("trustees", []),
                "subsidiaries": parsed.get("subsidiaries", []),
            },
        )
        self.db.add(entity)
        await self.db.flush()
        await self.db.refresh(entity)
        return entity
    
    async def _create_ownership(
        self,
        owner_id: UUID,
        owned_id: UUID,
        ownership_type: str,
        source: str,
        description: Optional[str] = None,
        percentage: Optional[float] = None,
    ) -> EntityOwnership:
        """Create ownership relationship if it doesn't exist."""
        # Check if relationship exists
        result = await self.db.execute(
            select(EntityOwnership)
            .where(EntityOwnership.owner_id == owner_id)
            .where(EntityOwnership.owned_id == owned_id)
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            return existing
        
        ownership = EntityOwnership(
            owner_id=owner_id,
            owned_id=owned_id,
            ownership_type=ownership_type,
            ownership_percentage=percentage,
            relationship_description=description,
            source=source,
            verified=True,
        )
        self.db.add(ownership)
        await self.db.flush()
        return ownership
    
    async def _entity_to_dict(self, entity: Entity) -> Dict[str, Any]:
        """Convert entity to dictionary representation."""
        return {
            "id": str(entity.id),
            "name": entity.resolved_name or entity.original_name,
            "original_name": entity.original_name,
            "entity_type": entity.entity_type.value if entity.entity_type else "unknown",
            "charity_number": entity.charity_number,
            "company_number": entity.company_number,
            "status": entity.charity_status,
            "level": entity.ownership_level,
            "income": entity.latest_income,
            "expenditure": entity.latest_expenditure,
        }
    
    def _count_tree_entities(self, nodes: List[Dict[str, Any]]) -> int:
        """Count total entities in a tree."""
        count = len(nodes)
        for node in nodes:
            count += self._count_tree_entities(node.get("children", []))
            count += self._count_tree_entities(node.get("parents", []))
        return count
    
    async def build_trees_for_batch(
        self,
        batch_id: UUID,
        max_depth: int = 3,
    ) -> Dict[str, Any]:
        """
        Build ownership trees for all matched entities in a batch.
        
        Args:
            batch_id: Batch ID
            max_depth: Maximum tree depth
        
        Returns:
            Summary of trees built
        """
        result = await self.db.execute(
            select(Entity)
            .where(Entity.batch_id == batch_id)
            .where(Entity.resolution_status == "matched")
            .where(Entity.ownership_level == 0)  # Only root entities
        )
        entities = result.scalars().all()
        
        trees_built = 0
        total_related = 0
        
        for entity in entities:
            try:
                # Reset visited sets for each entity
                self._visited_charities = set()
                self._visited_companies = set()
                
                tree = await self.build_tree_for_entity(
                    entity.id,
                    max_depth=max_depth,
                    direction="down",
                )
                trees_built += 1
                total_related += tree["total_entities"] - 1  # Exclude root
                
            except Exception as e:
                logger.error("Error building tree", entity_id=str(entity.id), error=str(e))
        
        await self.close()
        
        return {
            "batch_id": str(batch_id),
            "trees_built": trees_built,
            "total_related_entities": total_related,
        }
