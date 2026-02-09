.PHONY: help panel-deploy panel-restore panel-reboot panel-destroy node-deploy node-reboot node-destroy krisa-bot-deploy backup-setup

help:
	@echo "Available commands:"
	@echo "  make panel-deploy   - Deploy fresh Panel"
	@echo "  make panel-reboot   - Reboot Panel"
	@echo "  make panel-destroy  - Destroy Panel"
	@echo "  make panel-restore BACKUP=<backup_name> - Deploy Panel from BACKUP (panel secrets present in .env)"
	@echo "  make panel-restore BACKUP=<backup_name> NEW_SECRETS=1 - Deploy Panel from BACKUP (generate new panel secrets)"
	@echo "  make node-deploy    - Deploy Nodes"
	@echo "  make node-reboot    - Reboot Nodes"
	@echo "  make node-destroy   - Destroy Nodes"
	@echo "  make bot-krisa-deploy - Deploy Krisa Bot"
	@echo "  make bot-krisa-destroy - Destroy Krisa Bot DNS"
	@echo "  make bot-krisa-restore BACKUP=<backup_name> - Restore Krisa Bot from BACKUP"
	@echo "  make backup-setup   - Setup Daily Panel Backups (use KRISA=1 to include krisa bot)"
	@echo "  make backup-force   - Force Backup Creation (use KRISA=1 to include krisa bot)"

panel-deploy:
	.venv/bin/python orchestration/deploy.py panel deploy

panel-restore:
	.venv/bin/python orchestration/deploy.py panel restore $(BACKUP) $(if $(NEW_SECRETS),--new-panel-secrets,)

panel-reboot:
	.venv/bin/python orchestration/deploy.py panel reboot

panel-destroy:
	.venv/bin/python orchestration/deploy.py panel destroy

node-deploy:
	.venv/bin/python orchestration/deploy.py node deploy

node-reboot:
	.venv/bin/python orchestration/deploy.py node reboot

node-destroy:
	.venv/bin/python orchestration/deploy.py node destroy

bot-krisa-deploy:
	.venv/bin/python orchestration/deploy.py bot deploy krisa

bot-krisa-destroy:
	.venv/bin/python orchestration/deploy.py bot destroy krisa

bot-krisa-restore:
	.venv/bin/python orchestration/deploy.py bot restore krisa $(BACKUP)

backup-setup:
	.venv/bin/python orchestration/deploy.py backup setup $(if $(KRISA),--krisa,)

backup-force:
	.venv/bin/python orchestration/deploy.py backup force $(if $(KRISA),--krisa,)

