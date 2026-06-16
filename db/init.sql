CREATE USER chat_user WITH PASSWORD 'ChatUser@2024';

CREATE ROLE chatbot_role;
GRANT chatbot_role TO chat_admin;
GRANT chatbot_role TO chat_user;

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(64) UNIQUE NOT NULL,
    password_hash VARCHAR(256) NOT NULL,
    role VARCHAR(16) NOT NULL DEFAULT 'user',
    email VARCHAR(128),
    phone VARCHAR(32),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    title VARCHAR(256),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER REFERENCES conversations(id),
    role VARCHAR(16) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    raw_content TEXT NOT NULL,
    sanitized_content TEXT,
    pii_redacted BOOLEAN DEFAULT FALSE,
    pii_types_redacted TEXT[],
    image_data TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER,
    username VARCHAR(64),
    action_type VARCHAR(32) NOT NULL,
    table_name VARCHAR(64),
    record_id INTEGER,
    detail TEXT,
    ip_address VARCHAR(45),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_user ON audit_log(user_id);
CREATE INDEX idx_audit_time ON audit_log(created_at);
CREATE INDEX idx_messages_conversation ON messages(conversation_id);

GRANT USAGE, SELECT ON SEQUENCE users_id_seq TO chatbot_role;
GRANT USAGE, SELECT ON SEQUENCE conversations_id_seq TO chatbot_role;
GRANT USAGE, SELECT ON SEQUENCE messages_id_seq TO chatbot_role;
GRANT USAGE, SELECT ON SEQUENCE audit_log_id_seq TO chatbot_role;
GRANT SELECT, INSERT, UPDATE ON users TO chatbot_role;
GRANT SELECT, INSERT, UPDATE ON conversations TO chatbot_role;
GRANT SELECT, INSERT ON messages TO chatbot_role;
GRANT SELECT, INSERT ON audit_log TO chatbot_role;

CREATE USER audit_viewer WITH PASSWORD 'AuditView@2024';
GRANT SELECT ON audit_log TO audit_viewer;
