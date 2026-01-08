"""
Account Manager
Handles multiple student account management for course selection.
"""

import os
import json
import uuid
from dataclasses import dataclass, asdict
from typing import List, Optional


@dataclass
class Account:
    """Represents a student account."""
    id: str
    name: str
    username: str
    password: str
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Account':
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            name=data.get('name', ''),
            username=data.get('username', ''),
            password=data.get('password', '')
        )


class AccountManager:
    """Manages multiple student accounts."""
    
    DEFAULT_BASE_URL = ""  # Must be configured by user
    
    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), "config.json")
        self.config_path = config_path
        self.accounts: List[Account] = []
        self.default_account_id: Optional[str] = None
        self.base_url: str = self.DEFAULT_BASE_URL
        self._load()
    
    def _load(self):
        """Load accounts from config file."""
        if not os.path.exists(self.config_path):
            self.accounts = []
            self.default_account_id = None
            return
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Check if it's the new format (has 'accounts' key)
            if 'accounts' in config:
                self.accounts = [Account.from_dict(acc) for acc in config.get('accounts', [])]
                self.default_account_id = config.get('default_account')
                self.base_url = config.get('base_url', self.DEFAULT_BASE_URL)
            else:
                # Legacy format: single account with username/password at root
                self._migrate_legacy_config(config)
        except Exception as e:
            print(f"Error loading config: {e}")
            self.accounts = []
            self.default_account_id = None
    
    def _migrate_legacy_config(self, legacy_config: dict):
        """Convert old single-account config to new format."""
        username = legacy_config.get('username', '')
        password = legacy_config.get('password', '')
        
        if username:
            account = Account(
                id=str(uuid.uuid4()),
                name=f"账号1",
                username=username,
                password=password
            )
            self.accounts = [account]
            self.default_account_id = account.id
            # Save in new format
            self.save()
        else:
            self.accounts = []
            self.default_account_id = None
    
    def save(self):
        """Save accounts to config file."""
        config = {
            'accounts': [acc.to_dict() for acc in self.accounts],
            'default_account': self.default_account_id,
            'base_url': self.base_url
        }
        
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    
    def add_account(self, name: str, username: str, password: str) -> Account:
        """Add a new account."""
        account = Account(
            id=str(uuid.uuid4()),
            name=name,
            username=username,
            password=password
        )
        self.accounts.append(account)
        
        # Set as default if it's the first account
        if len(self.accounts) == 1:
            self.default_account_id = account.id
        
        self.save()
        return account
    
    def update_account(self, account_id: str, name: str = None, 
                       username: str = None, password: str = None) -> Optional[Account]:
        """Update an existing account."""
        account = self.get_account(account_id)
        if not account:
            return None
        
        if name is not None:
            account.name = name
        if username is not None:
            account.username = username
        if password is not None:
            account.password = password
        
        self.save()
        return account
    
    def remove_account(self, account_id: str) -> bool:
        """Remove an account by ID."""
        for i, acc in enumerate(self.accounts):
            if acc.id == account_id:
                self.accounts.pop(i)
                
                # Update default if we removed the default account
                if self.default_account_id == account_id:
                    self.default_account_id = self.accounts[0].id if self.accounts else None
                
                self.save()
                return True
        return False
    
    def get_account(self, account_id: str) -> Optional[Account]:
        """Get account by ID."""
        for acc in self.accounts:
            if acc.id == account_id:
                return acc
        return None
    
    def get_account_by_username(self, username: str) -> Optional[Account]:
        """Get account by username."""
        for acc in self.accounts:
            if acc.username == username:
                return acc
        return None
    
    def get_default_account(self) -> Optional[Account]:
        """Get the default account."""
        if self.default_account_id:
            return self.get_account(self.default_account_id)
        return self.accounts[0] if self.accounts else None
    
    def set_default_account(self, account_id: str) -> bool:
        """Set the default account."""
        if self.get_account(account_id):
            self.default_account_id = account_id
            self.save()
            return True
        return False
    
    def get_all_accounts(self) -> List[Account]:
        """Get all accounts."""
        return self.accounts.copy()
    
    def get_base_url(self) -> str:
        """Get the configured base URL."""
        return self.base_url
    
    def set_base_url(self, url: str) -> None:
        """Set the base URL."""
        self.base_url = url.rstrip('/') if url else self.DEFAULT_BASE_URL
        self.save()


if __name__ == "__main__":
    # Simple test
    manager = AccountManager()
    print(f"Loaded {len(manager.accounts)} accounts")
    for acc in manager.accounts:
        print(f"  - {acc.name}: {acc.username}")
