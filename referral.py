"""
Referral system functionality
"""

import logging
from urllib.parse import urlencode
from datetime import datetime, timedelta

from database import Database
from config import BOT_USERNAME, REFERRAL_BONUS_DURATION_HOURS

logger = logging.getLogger(__name__)

class ReferralHandler:
    def __init__(self, db: Database):
        self.db = db
    
    def generate_referral_link(self, user_id: int) -> str:
        """Generate referral link for a user"""
        # Create a Telegram deep link
        base_url = f"https://t.me/{BOT_USERNAME}"
        params = {'start': str(user_id)}
        
        referral_link = f"{base_url}?{urlencode(params)}"
        logger.info(f"Generated referral link for user {user_id}")
        
        return referral_link
    
    def process_referral(self, referrer_id: int, referred_id: int) -> bool:
        """Process a referral when a new user joins"""
        try:
            # Check if users exist
            referrer = self.db.get_or_create_user(referrer_id, None, None)
            if not referrer:
                logger.warning(f"Referrer {referrer_id} not found")
                return False
            
            # Check if referral already exists
            success = self.db.add_referral(referrer_id, referred_id)
            
            if success:
                logger.info(f"Processed referral: {referrer_id} -> {referred_id}")
                return True
            else:
                logger.warning(f"Referral already exists: {referrer_id} -> {referred_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error processing referral {referrer_id} -> {referred_id}: {e}")
            return False
    
    def get_referral_stats(self, user_id: int) -> dict:
        """Get referral statistics for a user"""
        referral_count = self.db.get_referral_count(user_id)
        bonus_downloads = self.db.get_bonus_downloads(user_id)
        earliest_expiry = self.db.get_earliest_bonus_expiry(user_id)
        
        return {
            'referral_count': referral_count,
            'bonus_downloads': bonus_downloads,
            'earliest_expiry': earliest_expiry
        }
    
    def calculate_bonus_expiry(self) -> datetime:
        """Calculate when a referral bonus should expire"""
        return datetime.now() + timedelta(hours=REFERRAL_BONUS_DURATION_HOURS)
    
    def is_valid_referrer(self, referrer_id: int, referred_id: int) -> bool:
        """Check if a referral is valid"""
        # Users can't refer themselves
        if referrer_id == referred_id:
            return False
        
        # Check if referral already exists
        with self.db.get_connection() as conn:
            cursor = conn.execute('''
                SELECT COUNT(*) as count FROM referrals 
                WHERE referrer_id = ? AND referred_id = ?
            ''', (referrer_id, referred_id))
            
            result = cursor.fetchone()
            existing_count = result['count'] if result else 0
            
            return existing_count == 0
    
    def get_referral_leaderboard(self, limit: int = 10) -> list:
        """Get top referrers"""
        with self.db.get_connection() as conn:
            cursor = conn.execute('''
                SELECT 
                    r.referrer_id,
                    u.username,
                    u.first_name,
                    COUNT(r.id) as referral_count
                FROM referrals r
                JOIN users u ON r.referrer_id = u.id
                GROUP BY r.referrer_id
                ORDER BY referral_count DESC
                LIMIT ?
            ''', (limit,))
            
            leaderboard = []
            for row in cursor.fetchall():
                leaderboard.append({
                    'user_id': row['referrer_id'],
                    'username': row['username'],
                    'first_name': row['first_name'],
                    'referral_count': row['referral_count']
                })
            
            return leaderboard
    
    def cleanup_expired_bonuses(self):
        """Clean up expired referral bonuses"""
        self.db.cleanup_expired_bonuses()
        logger.info("Cleaned up expired referral bonuses")
