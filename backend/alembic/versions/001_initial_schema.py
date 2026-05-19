"""Initial schema — incidents, ambulances, hospitals, contacts, dispatchers

Revision ID: 001_initial
Revises: 
Create Date: 2026-05-31
"""

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostGIS extension
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
    op.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";")

    # Enums
    op.execute("CREATE TYPE severity_level AS ENUM ('low', 'medium', 'critical');")
    op.execute("CREATE TYPE incident_status AS ENUM ('reported', 'dispatched', 'en_route', 'on_scene', 'hospital_handoff', 'closed');")
    op.execute("CREATE TYPE ambulance_status AS ENUM ('free', 'routing', 'on_scene');")

    # hospitals
    op.create_table(
        "hospitals",
        sa.Column("id",            sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("name",          sa.String(512), nullable=False),
        sa.Column("location",      Geometry(geometry_type="POINT", srid=4326), nullable=False),
        sa.Column("address",       sa.String(512)),
        sa.Column("phone",         sa.String(20)),
        sa.Column("trauma_level",  sa.Integer, default=2),
        sa.Column("beds_available",sa.Integer, default=0),
        sa.Column("is_active",     sa.Boolean, default=True),
        sa.Column("updated_at",    sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("idx_hospitals_location", "hospitals", ["location"], postgresql_using="gist")

    # ambulance_units
    op.create_table(
        "ambulance_units",
        sa.Column("id",          sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("unit_code",   sa.String(20), nullable=False, unique=True),
        sa.Column("location",    Geometry(geometry_type="POINT", srid=4326)),
        sa.Column("status",      sa.Text, nullable=False, server_default="free"),
        sa.Column("hospital_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("hospitals.id")),
        sa.Column("driver_name", sa.String(256)),
        sa.Column("driver_phone",sa.String(20)),
        sa.Column("is_active",   sa.Boolean, default=True),
        sa.Column("updated_at",  sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_ambulances_location", "ambulance_units", ["location"], postgresql_using="gist")
    op.create_index("idx_ambulances_status",   "ambulance_units", ["status"])

    # incidents
    op.create_table(
        "incidents",
        sa.Column("id",                   sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("location",             Geometry(geometry_type="POINT", srid=4326), nullable=False),
        sa.Column("address_approx",       sa.String(512)),
        sa.Column("photo_url",            sa.Text),
        sa.Column("photo_s3_key",         sa.String(512)),
        sa.Column("severity",             sa.Text, nullable=False, server_default="medium"),
        sa.Column("cnn_score",            sa.Float),
        sa.Column("cnn_confidence",       sa.Float),
        sa.Column("hotspot_risk",         sa.Float),
        sa.Column("status",               sa.Text, nullable=False, server_default="reported"),
        sa.Column("assigned_ambulance_id",sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("ambulance_units.id")),
        sa.Column("receiving_hospital_id",sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("hospitals.id")),
        sa.Column("device_id",            sa.String(256)),
        sa.Column("victim_language",      sa.String(10), server_default="en"),
        sa.Column("created_at",           sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("dispatched_at",        sa.DateTime(timezone=True)),
        sa.Column("on_scene_at",          sa.DateTime(timezone=True)),
        sa.Column("closed_at",            sa.DateTime(timezone=True)),
    )
    op.create_index("idx_incidents_location",   "incidents", ["location"], postgresql_using="gist")
    op.create_index("idx_incidents_status",     "incidents", ["status"])
    op.create_index("idx_incidents_created_at", "incidents", ["created_at"])

    # emergency_contacts
    op.create_table(
        "emergency_contacts",
        sa.Column("id",          sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("incident_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("incidents.id"), nullable=False),
        sa.Column("phone",       sa.String(20), nullable=False),
        sa.Column("name",        sa.String(256)),
        sa.Column("notified_at", sa.DateTime(timezone=True)),
        sa.Column("sms_sid",     sa.String(64)),
    )
    op.create_index("idx_contacts_incident", "emergency_contacts", ["incident_id"])

    # dispatchers
    op.create_table(
        "dispatchers",
        sa.Column("id",              sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("email",           sa.String(256), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(256), nullable=False),
        sa.Column("full_name",       sa.String(256)),
        sa.Column("is_active",       sa.Boolean, default=True),
        sa.Column("created_at",      sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("dispatchers")
    op.drop_table("emergency_contacts")
    op.drop_table("incidents")
    op.drop_table("ambulance_units")
    op.drop_table("hospitals")
    op.execute("DROP TYPE IF EXISTS ambulance_status;")
    op.execute("DROP TYPE IF EXISTS incident_status;")
    op.execute("DROP TYPE IF EXISTS severity_level;")
