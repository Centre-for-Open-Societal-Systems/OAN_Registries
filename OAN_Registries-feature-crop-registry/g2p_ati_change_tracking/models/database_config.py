import os
import psycopg2
import psycopg2.extras
import logging
from odoo import api, models, tools
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)
_ENSURED_AUDIT_DATABASES = set()


class AuditDatabaseManager(models.AbstractModel):
    """Manager for external audit database operations"""
    _name = 'g2p.change.log.database.manager'
    _description = 'Audit Database Manager'

    @api.model
    def _get_audit_db_config(self):
        """Get audit database configuration from system parameters"""
        config_param = self.env['ir.config_parameter'].sudo()
        return {
            'host': os.getenv('G2P_CHANGE_LOG_DB_HOST') or config_param.get_param('log_db.db.host', 'localhost'),
            'port': int(os.getenv('G2P_CHANGE_LOG_DB_PORT') or config_param.get_param('log_db.db.port', '5432')),
            'database': os.getenv('G2P_CHANGE_LOG_DB_NAME') or config_param.get_param('log_db.db.name', 'audit_logs'),
            'user': os.getenv('G2P_CHANGE_LOG_DB_USER') or config_param.get_param('log_db.db.user', 'audit_user'),
            'password': os.getenv('G2P_CHANGE_LOG_DB_PASSWORD') or config_param.get_param('log_db.db.password', ''),
        }

    @api.model
    def _get_audit_db_signature(self):
        config = self._get_audit_db_config()
        return (
            config["host"],
            config["port"],
            config["database"],
            config["user"],
        )

    @api.model
    def _get_audit_db_connection(self):
        """Get connection to external audit database"""
        try:
            config = self._get_audit_db_config()
            # print(f"🔧 Database config from Odoo: {config}")
            conn = psycopg2.connect(
                host=config['host'],
                port=config['port'],
                database=config['database'],
                user=config['user'],
                password=config['password']
            )
            conn.autocommit = False
            # print(f"🔧 Connected to database: {config['database']}")
            return conn
        except Exception as e:
            # print(f"❌ Failed to connect to audit database: {e}")
            _logger.error(f"Failed to connect to audit database: {e}")
            raise UserError(f"Cannot connect to audit database: {e}")

    @api.model
    def _ensure_audit_tables(self):
        """Ensure audit tables exist in external database"""
        signature = self._get_audit_db_signature()
        if signature in _ENSURED_AUDIT_DATABASES:
            return True

        conn = self._get_audit_db_connection()
        try:
            cursor = conn.cursor()
            
            # Create g2p_change_log table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS g2p_change_log (
                    id SERIAL PRIMARY KEY,
                    name TEXT,
                    model_id INTEGER,
                    model_name VARCHAR(255),
                    model_model VARCHAR(255),
                    res_id INTEGER,
                    user_id INTEGER,
                    method VARCHAR(64),
                    log_type VARCHAR(10),
                    http_session_id INTEGER,
                    http_request_id INTEGER,
                    create_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    write_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    create_uid INTEGER,
                    write_uid INTEGER
                )
            """)
            
            # Create g2p_change_log_line table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS g2p_change_log_line (
                    id SERIAL PRIMARY KEY,
                    log_id INTEGER REFERENCES g2p_change_log(id) ON DELETE CASCADE,
                    field_id INTEGER,
                    field_name VARCHAR(255),
                    field_description VARCHAR(255),
                    old_value TEXT,
                    new_value TEXT,
                    old_value_text TEXT,
                    new_value_text TEXT,
                    create_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    write_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    create_uid INTEGER,
                    write_uid INTEGER
                )
            """)

            # Keep existing databases in sync with the expected schema.
            cursor.execute("""
                ALTER TABLE g2p_change_log
                ALTER COLUMN name TYPE TEXT
            """)
            
            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_g2p_change_log_model_id ON g2p_change_log(model_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_g2p_change_log_res_id ON g2p_change_log(res_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_g2p_change_log_user_id ON g2p_change_log(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_g2p_change_log_create_date ON g2p_change_log(create_date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_g2p_change_log_line_log_id ON g2p_change_log_line(log_id)")
            
            conn.commit()
            _ENSURED_AUDIT_DATABASES.add(signature)
            _logger.info("Audit database tables created/verified successfully")
            
        except Exception as e:
            conn.rollback()
            _logger.error(f"Failed to create audit tables: {e}")
            raise UserError(f"Failed to create audit tables: {e}")
        finally:
            conn.close()

    @api.model
    def execute_audit_query(self, query, params=None, fetch=False):
        # """Execute query on audit database"""
        # print(f"🔧 Executing audit query: {query[:100]}...")
        # print(f"🔧 Query params: {params}")
        self._ensure_audit_tables()
        conn = self._get_audit_db_connection()
        try:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute(query, params or ())
            # print(f"🔧 Query executed successfully")

            if fetch:
                result = cursor.fetchall()
                # print(f"🔧 Fetched {len(result)} rows: {result}")
                conn.commit()  # Commit the transaction even when fetching
                # print(f"🔧 Transaction committed")
                return [dict(row) for row in result]
            else:
                rowcount = cursor.rowcount
                conn.commit()
                # print(f"🔧 Query affected {rowcount} rows, transaction committed")
                return rowcount

        except psycopg2.errors.UndefinedTable as e:
            # print(f"🔧 Table doesn't exist, creating audit tables...")
            conn.rollback()
            # Create tables and retry
            self._ensure_audit_tables()
            # Retry the query
            return self.execute_audit_query(query, params, fetch)
        except Exception as e:
            # print(f"❌ Audit database query failed: {e}")
            conn.rollback()
            _logger.error(f"Audit database query failed: {e}")
            raise UserError(f"Audit database query failed: {e}")
        finally:
            conn.close()
