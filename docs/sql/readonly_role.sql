-- Least-privilege role for the agent's tools (docs/SECURITY.md).
-- The tools only ever READ the provider directory. This role can do exactly that:
-- SELECT on the four provider tables (+ the M2M join), nothing on chat/assistant
-- tables, no writes anywhere. Point DATABASE_URL_READONLY at it.
--
-- Run as the database owner / admin, AFTER `manage.py migrate`:
--   psql "$DATABASE_URL" -v tools_password="'change-me'" -f docs/sql/readonly_role.sql

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'healtrip_tools') THEN
    CREATE ROLE healtrip_tools LOGIN;
  END IF;
END $$;

ALTER ROLE healtrip_tools PASSWORD :tools_password;
-- Belt and braces: every transaction on this role is read-only.
ALTER ROLE healtrip_tools SET default_transaction_read_only = on;

REVOKE ALL ON ALL TABLES IN SCHEMA public FROM healtrip_tools;
GRANT USAGE ON SCHEMA public TO healtrip_tools;
GRANT SELECT ON
  providers_specialty,
  providers_hospital,
  providers_doctor,
  providers_doctor_specialties,
  providers_availabilityslot
TO healtrip_tools;
