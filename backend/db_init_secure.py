# db_init_secure.py - Secure Database Initialization (SQL Injection Fix)
"""
Fixes the SQL injection vulnerability in init_db() by properly validating
all column names before using them in SQL statements.
"""

import sqlite3
import re
from typing import List
from schema import SCHEMA_ENTITY_FIELDS, LP_PREFIX, LP_COUNT

# SQL Injection Prevention - Whitelist for identifiers
ALLOWED_SQL_IDENTIFIER = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_\s&(),-]*$')

def validate_and_quote_identifier(identifier: str) -> str:
    """
    Validate SQL identifier and return properly quoted version.
    Raises ValueError if identifier contains suspicious patterns.
    """
    # Allow alphanumeric, underscore, spaces, and common punctuation in column names
    if not ALLOWED_SQL_IDENTIFIER.match(identifier):
        raise ValueError(f"Invalid SQL identifier: {identifier}")
    
    # Properly quote the identifier
    return '"' + identifier.replace('"', '""') + '"'

def get_all_schema_fields() -> List[str]:
    """Generate all schema fields (entity + linked parties)"""
    linked_cols = []
    for i in range(1, LP_COUNT + 1):
        for _, prefix in LP_PREFIX.items():
            linked_cols.append(f"{prefix}{i}")
    return SCHEMA_ENTITY_FIELDS + linked_cols

def build_create_table_sql() -> str:
    """
    Safely build CREATE TABLE SQL with validated identifiers.
    This prevents SQL injection by validating each column name.
    """
    all_fields = get_all_schema_fields()
    
    # Validate ALL identifiers before building SQL
    validated_fields = []
    for field in all_fields:
        try:
            quoted = validate_and_quote_identifier(field)
            validated_fields.append(f"{quoted} TEXT")
        except ValueError as e:
            print(f"[SECURITY WARNING] Skipping invalid field: {e}")
            continue
    
    fields_sql = ",\n            ".join(validated_fields)
    
    # Build the CREATE TABLE statement with validated fields
    create_sql = f"""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,

            -- matching/workflow meta
            input_name TEXT NOT NULL,
            name_hash TEXT,
            pipeline_status TEXT NOT NULL,
            match_type TEXT,
            company_number TEXT,
            company_status TEXT,
            confidence REAL,
            reason TEXT,
            search_url TEXT,
            source_url TEXT,
            retrieved_at TEXT,
            candidates_json TEXT,
            enrich_status TEXT DEFAULT 'pending',
            enrich_json_path TEXT,
            enrich_xlsx_path TEXT,
            shareholders_json TEXT,
            shareholders_status TEXT,
            ownership_tree_json TEXT,
            out_dir TEXT,
            created_at TEXT NOT NULL,
            resolved_registry TEXT,
            charity_number TEXT,
            svg_path TEXT,

            -- ==== BEGIN: EXACT client-upload schema (validated) ====
            {fields_sql}
            -- ==== END: EXACT client-upload schema ====

            ,
            -- legacy freeform (used by UI and inserts; safe to keep)
            client_ref TEXT,
            client_address TEXT,
            client_address_city TEXT,
            client_address_postcode TEXT,
            client_address_country TEXT,
            client_linked_parties TEXT,
            client_notes TEXT,

            FOREIGN KEY(run_id) REFERENCES runs(id)
        )
    """
    
    return create_sql

def init_db_secure(db_context_manager):
    """
    Secure database initialization with SQL injection prevention.
    
    Args:
        db_context_manager: Database context manager (from database_config)
    """
    print("[SECURITY] Initializing database with validated schema...")
    
    with db_context_manager() as conn:
        c = conn.cursor()
        
        # Create runs table
        c.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                upload_filename TEXT
            )
        """)
        
        # Create items table with validated schema
        create_sql = build_create_table_sql()
        c.execute(create_sql)
        
        # Get existing columns
        existing_cols_lower = {
            r["name"].lower()
            for r in conn.execute("PRAGMA table_info(items)").fetchall()
        }
        
        # Add any missing schema columns using ALTER TABLE (safer than string interpolation)
        all_fields = get_all_schema_fields()
        for field in all_fields:
            try:
                if field.lower() not in existing_cols_lower:
                    quoted_field = validate_and_quote_identifier(field)
                    # Use parameterized query structure (though ALTER TABLE doesn't support ?, we validate the identifier)
                    conn.execute(f'ALTER TABLE items ADD COLUMN {quoted_field} TEXT')
                    existing_cols_lower.add(field.lower())
            except ValueError as e:
                print(f"[SECURITY WARNING] Skipping invalid field in ALTER: {e}")
            except sqlite3.OperationalError:
                # Column already exists or other error
                pass
        
        # Add legacy freeform columns if missing
        legacy_cols = [
            "client_ref", "client_address", "client_address_city",
            "client_address_postcode", "client_address_country",
            "client_linked_parties", "client_notes"
        ]
        
        for col in legacy_cols:
            if col.lower() not in existing_cols_lower:
                try:
                    quoted_col = validate_and_quote_identifier(col)
                    conn.execute(f'ALTER TABLE items ADD COLUMN {quoted_col} TEXT')
                    existing_cols_lower.add(col.lower())
                except (ValueError, sqlite3.OperationalError):
                    pass
        
        # Create indexes
        c.execute("CREATE INDEX IF NOT EXISTS idx_items_run ON items(run_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_items_namehash ON items(name_hash)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_items_status ON items(pipeline_status)")
        
        # Create users table (if not exists)
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                hashed_password TEXT NOT NULL,
                full_name TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT
            )
        """)
        
        # Create roles table
        c.execute("""
            CREATE TABLE IF NOT EXISTS roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT
            )
        """)
        
        # Create user_roles junction table
        c.execute("""
            CREATE TABLE IF NOT EXISTS user_roles (
                user_id INTEGER NOT NULL,
                role_id INTEGER NOT NULL,
                PRIMARY KEY (user_id, role_id),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE
            )
        """)
        
        # Create token blacklist table
        c.execute("""
            CREATE TABLE IF NOT EXISTS token_blacklist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT NOT NULL UNIQUE,
                user_id INTEGER,
                blacklisted_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                reason TEXT
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_token_blacklist_token ON token_blacklist(token)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_token_blacklist_expires ON token_blacklist(expires_at)")
        
        # Create audit logs table
        c.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                user_id INTEGER,
                user_email TEXT,
                action TEXT NOT NULL,
                resource_type TEXT,
                resource_id TEXT,
                ip_address TEXT,
                user_agent TEXT,
                status TEXT DEFAULT 'success',
                details TEXT
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_logs(user_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs(action)")
        
        # Insert default roles if they don't exist
        default_roles = [
            ('admin', 'Administrator with full access'),
            ('user', 'Regular user with standard access'),
            ('viewer', 'Read-only access')
        ]
        
        for role_name, description in default_roles:
            try:
                c.execute("INSERT INTO roles (name, description) VALUES (?, ?)", (role_name, description))
            except sqlite3.IntegrityError:
                # Role already exists
                pass
        
        conn.commit()
        print("[SECURITY] Database initialization complete with validated schema")

# Export for use in app.py
__all__ = ['init_db_secure', 'validate_and_quote_identifier']
