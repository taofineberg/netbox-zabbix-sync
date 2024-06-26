## Used to get secrets from HashiCorp Vault

import os
import sys
import logging
import hvac
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient


credential = DefaultAzureCredential()
# Azure Key Vault
AZURE_KEY_VAULT_URL = os.getenv('AZURE_KEY_VAULT_URL')

# Get secret from Azure Key Vault for HCP Vault Token
secret_name = os.getenv('HCP_VAULT_TOKEN_Azure_Keystore_name')
secret_client = SecretClient(vault_url=AZURE_KEY_VAULT_URL, credential=credential)
retrieved_secret_HCP_VAULT = secret_client.get_secret(secret_name)




def read_vault_credentials():
    """Read Vault credentials from environment variables."""
    vault_url = os.getenv('VAULT_URL')
    vault_token = retrieved_secret_HCP_VAULT.value 
    mount_point = os.getenv('MOUNT_POINT')
    
    if not vault_url or not vault_token or not mount_point:
        raise ValueError("Environment variables for Vault credentials are not set properly.")
    
    return vault_url, vault_token, mount_point

def get_vault_credentials(vault_url, vault_token, mount_point, secret_path):
    """Retrieve secrets from Vault."""
    try:
        client = hvac.Client(url=vault_url, token=vault_token)
        secret = client.secrets.kv.v2.read_secret_version(
            mount_point=mount_point,
            path=secret_path,
            raise_on_deleted_version=True
        )
        return secret['data']['data']
    except hvac.exceptions.Forbidden:
        logging.error("Permission denied. Check if the token has read access to the specified path.")
        sys.exit(1)
    except Exception as e:
        logging.error(f"An error occurred while retrieving secrets from Vault: {e}")
        sys.exit(1)