"""
Database models and operations for the Telegram bot
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class User:
    id: int
    username: Optional[str]
    first_name: Optional[str]
    total_downloads: int
    created_at: datetime
    last_active: datetime

@dataclass
class Download:
    id: int
    user_id: int
    url: str
    filename: str
    file_size: int
    created_at: datetime

@dataclass
class Referral:
    id: int
    referrer_id: int
    referred_id: int
    created_at: datetime
    bonus_expires_at: datetime

class Database:
    def __init__(self, db_path: str = 'bot_database.db'):
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_database(self):
        """Initialize database tables"""
        with self.get_connection() as conn:
            # Users table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    total_downloads INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Downloads table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS downloads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    url TEXT,
                    filename TEXT,
                    file_size INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            
            # Referrals table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS referrals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    referrer_id INTEGER,
                    referred_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    bonus_expires_at TIMESTAMP,
                    FOREIGN KEY (referrer_id) REFERENCES users (id),
                    FOREIGN KEY (referred_id) REFERENCES users (id),
                    UNIQUE (referrer_id, referred_id)
                )
            ''')
            
            # Create indexes
            conn.execute('CREATE INDEX IF NOT EXISTS idx_downloads_user_date ON downloads (user_id, created_at)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON referrals (referrer_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_referrals_expires ON referrals (bonus_expires_at)')
            
            conn.commit()
        
        logger.info("Database initialized successfully")
    
    def get_or_create_user(self, user_id: int, username: Optional[str], first_name: Optional[str]) -> User:
        """Get existing user or create new one"""
        with self.get_connection() as conn:
            # Try to get existing user
            cursor = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,))
            row = cursor.fetchone()
            
            if row:
                # Update user info and last_active
                conn.execute('''
                    UPDATE users 
                    SET username = ?, first_name = ?, last_active = CURRENT_TIMESTAMP 
                    WHERE id = ?
                ''', (username, first_name, user_id))
                conn.commit()
                
                return User(
                    id=row['id'],
                    username=row['username'],
                    first_name=row['first_name'],
                    total_downloads=row['total_downloads'],
                    created_at=datetime.fromisoformat(row['created_at']),
                    last_active=datetime.now()
                )
            else:
                # Create new user
                conn.execute('''
                    INSERT INTO users (id, username, first_name, total_downloads)
                    VALUES (?, ?, ?, 0)
                ''', (user_id, username, first_name))
                conn.commit()
                
                return User(
                    id=user_id,
                    username=username,
                    first_name=first_name,
                    total_downloads=0,
                    created_at=datetime.now(),
                    last_active=datetime.now()
                )
    
    def record_download(self, user_id: int, url: str, filename: str = '', file_size: int = 0):
        """Record a download and increment user's total"""
        with self.get_connection() as conn:
            # Insert download record
            conn.execute('''
                INSERT INTO downloads (user_id, url, filename, file_size)
                VALUES (?, ?, ?, ?)
            ''', (user_id, url, filename, file_size))
            
            # Increment user's total downloads
            conn.execute('''
                UPDATE users 
                SET total_downloads = total_downloads + 1, last_active = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (user_id,))
            
            conn.commit()
        
        logger.info(f"Recorded download for user {user_id}: {url}")
    
    def get_today_downloads_count(self, user_id: int) -> int:
        """Get number of downloads today for a user"""
        today = datetime.now().date()
        tomorrow = today + timedelta(days=1)
        
        with self.get_connection() as conn:
            cursor = conn.execute('''
                SELECT COUNT(*) as count
                FROM downloads 
                WHERE user_id = ? AND date(created_at) = date('now')
            ''', (user_id,))
            
            result = cursor.fetchone()
            return result['count'] if result else 0
    
    def get_user_stats(self) -> dict:
        """Get overall user statistics"""
        with self.get_connection() as conn:
            # Total users
            cursor = conn.execute('SELECT COUNT(*) as count FROM users')
            total_users = cursor.fetchone()['count']
            
            # Active users today
            cursor = conn.execute('''
                SELECT COUNT(*) as count FROM users 
                WHERE date(last_active) = date('now')
            ''')
            active_today = cursor.fetchone()['count']
            
            # Total downloads
            cursor = conn.execute('SELECT COUNT(*) as count FROM downloads')
            total_downloads = cursor.fetchone()['count']
            
            # Downloads today
            cursor = conn.execute('''
                SELECT COUNT(*) as count FROM downloads 
                WHERE date(created_at) = date('now')
            ''')
            downloads_today = cursor.fetchone()['count']
            
            return {
                'total_users': total_users,
                'active_today': active_today,
                'total_downloads': total_downloads,
                'downloads_today': downloads_today
            }
    
    def get_top_users(self, limit: int = 10) -> List[User]:
        """Get top users by download count"""
        with self.get_connection() as conn:
            cursor = conn.execute('''
                SELECT * FROM users 
                ORDER BY total_downloads DESC 
                LIMIT ?
            ''', (limit,))
            
            users = []
            for row in cursor.fetchall():
                users.append(User(
                    id=row['id'],
                    username=row['username'],
                    first_name=row['first_name'],
                    total_downloads=row['total_downloads'],
                    created_at=datetime.fromisoformat(row['created_at']),
                    last_active=datetime.fromisoformat(row['last_active'])
                ))
            
            return users
    
    def add_referral(self, referrer_id: int, referred_id: int):
        """Add a referral relationship"""
        bonus_expires_at = datetime.now() + timedelta(hours=24)
        
        with self.get_connection() as conn:
            try:
                conn.execute('''
                    INSERT INTO referrals (referrer_id, referred_id, bonus_expires_at)
                    VALUES (?, ?, ?)
                ''', (referrer_id, referred_id, bonus_expires_at))
                conn.commit()
                logger.info(f"Added referral: {referrer_id} -> {referred_id}")
                return True
            except sqlite3.IntegrityError:
                # Referral already exists
                logger.warning(f"Referral already exists: {referrer_id} -> {referred_id}")
                return False
    
    def get_referral_count(self, user_id: int) -> int:
        """Get number of successful referrals for a user"""
        with self.get_connection() as conn:
            cursor = conn.execute('''
                SELECT COUNT(*) as count FROM referrals WHERE referrer_id = ?
            ''', (user_id,))
            
            result = cursor.fetchone()
            return result['count'] if result else 0
    
    def get_bonus_downloads(self, user_id: int) -> int:
        """Get current bonus downloads for a user"""
        with self.get_connection() as conn:
            cursor = conn.execute('''
                SELECT COUNT(*) as count FROM referrals 
                WHERE referrer_id = ? AND bonus_expires_at > datetime('now')
            ''', (user_id,))
            
            result = cursor.fetchone()
            return result['count'] if result else 0
    
    def get_earliest_bonus_expiry(self, user_id: int) -> Optional[datetime]:
        """Get the earliest bonus expiry time for a user"""
        with self.get_connection() as conn:
            cursor = conn.execute('''
                SELECT MIN(bonus_expires_at) as earliest_expiry FROM referrals 
                WHERE referrer_id = ? AND bonus_expires_at > datetime('now')
            ''', (user_id,))
            
            result = cursor.fetchone()
            if result and result['earliest_expiry']:
                return datetime.fromisoformat(result['earliest_expiry'])
            return None
    
    def cleanup_expired_bonuses(self):
        """Clean up expired referral bonuses"""
        with self.get_connection() as conn:
            cursor = conn.execute('''
                DELETE FROM referrals WHERE bonus_expires_at <= datetime('now')
            ''')
            deleted_count = cursor.rowcount
            conn.commit()
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} expired referral bonuses")
    
    def get_all_user_ids(self) -> List[int]:
        """Get all user IDs"""
        with self.get_connection() as conn:
            cursor = conn.execute('SELECT id FROM users')
            return [row['id'] for row in cursor.fetchall()]
