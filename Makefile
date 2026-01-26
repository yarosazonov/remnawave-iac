.PHONY: help panel-deploy panel-restore panel-reboot panel-destroy node-deploy node-reboot node-destroy

help:
	@echo "Available commands:"
	@echo "  make panel-deploy   - Deploy fresh Panel (Terraform + Ansible)"
	@echo "  make panel-restore BACKUP=<backup_name> - Deploy Panel from backup (panel secrets present in .env)"
	@echo "  make panel-restore BACKUP=<backup_name> NEW_PANEL_SECRETS=1 - Deploy Panel from backup (generate new panel secrets)"
	@echo "  make panel-reboot   - Reboot Panel"
	@echo "  make panel-destroy  - Destroy Panel"
	@echo "  make node-deploy    - Deploy Nodes (Terraform + Ansible)"
	@echo "  make node-reboot    - Reboot Nodes"
	@echo "  make node-destroy   - Destroy Nodes"

panel-deploy:
	.venv/bin/python orchestration/deploy.py panel deploy

panel-restore:
	.venv/bin/python orchestration/deploy.py panel restore $(BACKUP) $(if $(NEW_PANEL_SECRETS),--new-panel-secrets,)

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

