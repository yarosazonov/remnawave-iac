.PHONY: help deploy deploy-reboot deploy-apply deploy-destroy

help:
	@echo "Available commands:"
	@echo "  make deploy         - Full deployment (Terraform + Ansible)"
	@echo "  make deploy-apply   - Infrastructure only (Terraform apply)"
	@echo "  make deploy-reboot  - Reboot all nodes"
	@echo "  make deploy-destroy - Destroy all infrastructure"

deploy:
	.venv/bin/python orchestration/deploy.py

deploy-reboot:
	.venv/bin/python orchestration/deploy.py reboot

deploy-apply:
	.venv/bin/python orchestration/deploy.py apply

deploy-destroy:
	.venv/bin/python orchestration/deploy.py destroy
