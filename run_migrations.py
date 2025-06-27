import sys
import os

# Add the 'backend' directory to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from alembic.config import Config
from alembic import command

# Get the absolute path to the alembic.ini file
alembic_ini_path = os.path.join(os.path.dirname(__file__), 'backend', 'open_webui', 'alembic.ini')

# Create an Alembic configuration object
alembic_cfg = Config(alembic_ini_path)

# Set the script location dynamically to the correct migrations folder
migrations_path = os.path.join(os.path.dirname(__file__), 'backend', 'open_webui', 'migrations')
alembic_cfg.set_main_option("script_location", migrations_path)

# Run the upgrade command to the specific revision for agents table
command.upgrade(alembic_cfg, "d488d31a738e")

print("Migrations applied successfully.")
