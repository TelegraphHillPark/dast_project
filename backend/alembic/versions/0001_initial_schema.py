"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-27 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    userrole = sa.Enum('admin', 'user', name='userrole')
    scanstatus = sa.Enum('pending', 'running', 'paused', 'finished', 'failed', name='scanstatus')
    vulntype = sa.Enum(
        'sqli', 'xss', 'ssrf', 'open_redirect', 'header_injection',
        'broken_auth', 'sensitive_data', 'security_misconfiguration', 'other',
        name='vulntype',
    )
    vulnseverity = sa.Enum('critical', 'high', 'medium', 'low', 'info', name='vulnseverity')

    op.create_table(
        'users',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('username', sa.String(64), nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('role', userrole, nullable=False, server_default='user'),
        sa.Column('avatar_url', sa.String(512), nullable=True),
        sa.Column('totp_secret', sa.String(64), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('email', name='uq_users_email'),
        sa.UniqueConstraint('username', name='uq_users_username'),
    )
    op.create_index('ix_users_email', 'users', ['email'])
    op.create_index('ix_users_username', 'users', ['username'])

    op.create_table(
        'user_sessions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('token_hash', sa.String(255), nullable=False),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('token_hash', name='uq_user_sessions_token_hash'),
    )
    op.create_index('ix_user_sessions_user_id', 'user_sessions', ['user_id'])
    op.create_index('ix_user_sessions_token_hash', 'user_sessions', ['token_hash'])

    op.create_table(
        'api_tokens',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('owner_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('token_hash', sa.String(64), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('token_hash', name='uq_api_tokens_token_hash'),
    )
    op.create_index('ix_api_tokens_owner_id', 'api_tokens', ['owner_id'])
    op.create_index('ix_api_tokens_token_hash', 'api_tokens', ['token_hash'])

    op.create_table(
        'wordlists',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('owner_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('file_path', sa.String(1024), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('is_builtin', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_wordlists_owner_id', 'wordlists', ['owner_id'])

    op.create_table(
        'scans',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('owner_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('target_url', sa.String(2048), nullable=False),
        sa.Column('status', scanstatus, nullable=False, server_default='pending'),
        sa.Column('max_depth', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('timeout_seconds', sa.Integer(), nullable=False, server_default='3600'),
        sa.Column('excluded_paths', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('config', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_scans_owner_id', 'scans', ['owner_id'])
    op.create_index('ix_scans_status', 'scans', ['status'])

    op.create_table(
        'vulnerabilities',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('scan_id', sa.String(36), sa.ForeignKey('scans.id', ondelete='CASCADE'), nullable=False),
        sa.Column('vuln_type', vulntype, nullable=False),
        sa.Column('severity', vulnseverity, nullable=False),
        sa.Column('url', sa.String(2048), nullable=False),
        sa.Column('parameter', sa.String(255), nullable=True),
        sa.Column('method', sa.String(10), nullable=False, server_default='GET'),
        sa.Column('payload', sa.Text(), nullable=True),
        sa.Column('evidence', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('recommendation', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_vulnerabilities_scan_id', 'vulnerabilities', ['scan_id'])
    op.create_index('ix_vulnerabilities_vuln_type', 'vulnerabilities', ['vuln_type'])
    op.create_index('ix_vulnerabilities_severity', 'vulnerabilities', ['severity'])


def downgrade() -> None:
    op.drop_table('vulnerabilities')
    op.drop_table('scans')
    op.drop_table('wordlists')
    op.drop_table('api_tokens')
    op.drop_table('user_sessions')
    op.drop_table('users')

    sa.Enum(name='vulnseverity').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='vulntype').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='scanstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='userrole').drop(op.get_bind(), checkfirst=True)
