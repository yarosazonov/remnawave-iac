.PHONY: help panel-deploy panel-reboot panel-destroy nodes-deploy nodes-reboot nodes-destroy

help:
	@echo "Available commands:"
	@echo "  make panel-deploy   - Deploy Panel (Terraform + Ansible)"
	@echo "  make panel-reboot   - Reboot Panel"
	@echo "  make panel-destroy  - Destroy Panel"
	@echo "  make nodes-deploy   - Deploy Nodes (Terraform + Ansible)"
	@echo "  make nodes-reboot   - Reboot Nodes"
	@echo "  make nodes-destroy  - Destroy Nodes"

panel-deploy:
	.venv/bin/python orchestration/deploy.py panel deploy

panel-reboot:
	.venv/bin/python orchestration/deploy.py panel reboot

panel-destroy:
	.venv/bin/python orchestration/deploy.py panel destroy

nodes-deploy:
	.venv/bin/python orchestration/deploy.py nodes deploy

nodes-reboot:
	.venv/bin/python orchestration/deploy.py nodes reboot

nodes-destroy:
	.venv/bin/python orchestration/deploy.py nodes destroy

