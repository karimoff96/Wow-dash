"""
Centralized Archive Configuration

This file contains all archiving settings that apply to ALL centers.
You can modify these values at any time without touching code.

For environment-specific overrides, use .env file.
"""
import os
from pathlib import Path


class ArchiveConfig:
    """
    Central configuration for file archiving system.
    All settings here apply to ALL centers unless overridden in .env
    """
    
    # =============================================================================
    # ARCHIVING SCHEDULE & TIMING
    # =============================================================================
    
    # Minimum age (in days) for completed orders to be eligible for archiving
    # Recommendation: 7-30 days (shorter = more storage savings)
    MIN_AGE_DAYS = int(os.getenv('ARCHIVE_MIN_AGE_DAYS', '30'))
    
    # =============================================================================
    # SIZE THRESHOLDS
    # =============================================================================
    
    # Minimum total size (in MB) before triggering automatic archiving
    # Set to 0 to archive regardless of size
    # Recommendation: 50-100 MB
    MIN_SIZE_MB = int(os.getenv('ARCHIVE_MIN_SIZE_MB', '100'))
    
    # Maximum archive size (in MB) - splits into multiple archives if exceeded
    # Telegram limit is 2GB, we keep it lower for reliability
    # Recommendation: 500-1500 MB
    MAX_SIZE_MB = int(os.getenv('ARCHIVE_MAX_SIZE_MB', '1500'))
    
    # Maximum orders per archive (helps with splitting large batches)
    # Set to 0 for unlimited
    # Recommendation: 100-500 orders
    MAX_ORDERS_PER_BATCH = int(os.getenv('ARCHIVE_MAX_ORDERS_PER_BATCH', '500'))
    
    # =============================================================================
    # COMPRESSION SETTINGS
    # =============================================================================
    
    # ZIP compression level (0-9)
    # 0 = No compression (fastest, largest)
    # 6 = Balanced (recommended for mixed content)
    # 9 = Maximum compression (slowest, smallest)
    # Recommendation: 6 for general use, 9 if storage is critical
    COMPRESSION_LEVEL = int(os.getenv('ARCHIVE_COMPRESSION_LEVEL', '6'))
    
    # =============================================================================
    # FILE MANAGEMENT
    # =============================================================================
    
    # Whether to delete local files after successful archiving
    # True = Delete files (saves storage immediately)
    # False = Keep files locally (use more storage but faster access)
    DELETE_LOCAL_FILES = os.getenv('ARCHIVE_DELETE_LOCAL_FILES', 'True').lower() == 'true'
    
    # Keep archive files locally for X days before deletion (0=delete immediately)
    # This is for the temporary archive .zip before upload, not the order files
    LOCAL_RETENTION_DAYS = int(os.getenv('ARCHIVE_LOCAL_RETENTION_DAYS', '0'))
    
    # =============================================================================
    # ADVANCED OPTIONS
    # =============================================================================
    
    # Enable dry-run mode globally (for testing)
    # When True, creates archives but doesn't upload or delete files
    DRY_RUN_MODE = os.getenv('ARCHIVE_DRY_RUN_MODE', 'False').lower() == 'true'
    
    # Archive naming pattern
    # Available variables: {year}, {month}, {center_name}, {timestamp}
    ARCHIVE_NAME_PATTERN = os.getenv(
        'ARCHIVE_NAME_PATTERN', 
        'Archive_{year}-{month}_{center_name}'
    )
    
    # Skip archiving for centers without configured channel
    SKIP_UNCONFIGURED_CENTERS = os.getenv(
        'ARCHIVE_SKIP_UNCONFIGURED_CENTERS', 'True'
    ).lower() == 'true'
    
    # =============================================================================
    # HELPER METHODS
    # =============================================================================
    
    @classmethod
    def get_all_settings(cls):
        """Get all current settings as a dictionary"""
        return {
            'MIN_AGE_DAYS': cls.MIN_AGE_DAYS,
            'MIN_SIZE_MB': cls.MIN_SIZE_MB,
            'MAX_SIZE_MB': cls.MAX_SIZE_MB,
            'MAX_ORDERS_PER_BATCH': cls.MAX_ORDERS_PER_BATCH,
            'COMPRESSION_LEVEL': cls.COMPRESSION_LEVEL,
            'DELETE_LOCAL_FILES': cls.DELETE_LOCAL_FILES,
            'LOCAL_RETENTION_DAYS': cls.LOCAL_RETENTION_DAYS,
            'DRY_RUN_MODE': cls.DRY_RUN_MODE,
            'ARCHIVE_NAME_PATTERN': cls.ARCHIVE_NAME_PATTERN,
            'SKIP_UNCONFIGURED_CENTERS': cls.SKIP_UNCONFIGURED_CENTERS,
        }
    
    @classmethod
    def display_settings(cls):
        """Display current settings in readable format"""
        settings = cls.get_all_settings()
        print("=" * 60)
        print("CURRENT ARCHIVE CONFIGURATION")
        print("=" * 60)
        for key, value in settings.items():
            print(f"{key:.<40} {value}")
        print("=" * 60)
        return settings
    
    @classmethod
    def validate_settings(cls):
        """Validate configuration and return warnings"""
        warnings = []
        
        if cls.MIN_AGE_DAYS < 1:
            warnings.append("⚠️  MIN_AGE_DAYS is less than 1 day - might archive too aggressively")
        
        if cls.MAX_SIZE_MB > 1900:
            warnings.append("⚠️  MAX_SIZE_MB exceeds recommended 1500MB - might fail Telegram uploads")
        
        if cls.COMPRESSION_LEVEL not in range(10):
            warnings.append(f"❌ COMPRESSION_LEVEL must be 0-9, got {cls.COMPRESSION_LEVEL}")
        
        if cls.MIN_SIZE_MB > cls.MAX_SIZE_MB:
            warnings.append("❌ MIN_SIZE_MB cannot be greater than MAX_SIZE_MB")
        
        if not warnings:
            warnings.append("✅ All settings are valid")
        
        return warnings


# =============================================================================
# QUICK CONFIGURATION PRESETS
# =============================================================================

class ArchivePresets:
    """Pre-configured settings for common scenarios"""
    
    AGGRESSIVE = {
        'MIN_AGE_DAYS': 3,
        'MIN_SIZE_MB': 10,
        'MAX_SIZE_MB': 500,
        'MAX_ORDERS_PER_BATCH': 100,
        'COMPRESSION_LEVEL': 9,
        'DELETE_LOCAL_FILES': True,
    }
    
    BALANCED = {
        'MIN_AGE_DAYS': 7,
        'MIN_SIZE_MB': 50,
        'MAX_SIZE_MB': 800,
        'MAX_ORDERS_PER_BATCH': 200,
        'COMPRESSION_LEVEL': 6,
        'DELETE_LOCAL_FILES': True,
    }
    
    CONSERVATIVE = {
        'MIN_AGE_DAYS': 30,
        'MIN_SIZE_MB': 100,
        'MAX_SIZE_MB': 1500,
        'MAX_ORDERS_PER_BATCH': 500,
        'COMPRESSION_LEVEL': 3,
        'DELETE_LOCAL_FILES': False,
    }
    
    @classmethod
    def apply_preset(cls, preset_name):
        """
        Apply a preset configuration
        
        Usage:
            ArchivePresets.apply_preset('AGGRESSIVE')
        """
        presets = {
            'AGGRESSIVE': cls.AGGRESSIVE,
            'BALANCED': cls.BALANCED,
            'CONSERVATIVE': cls.CONSERVATIVE,
        }
        
        if preset_name.upper() not in presets:
            raise ValueError(f"Unknown preset: {preset_name}. Choose from: {list(presets.keys())}")
        
        preset = presets[preset_name.upper()]
        
        print(f"\n📋 Applying '{preset_name.upper()}' preset...")
        print("=" * 60)
        for key, value in preset.items():
            print(f"  {key}: {value}")
        print("=" * 60)
        print("\n⚠️  To make this permanent, add these to your .env file:")
        for key, value in preset.items():
            print(f"ARCHIVE_{key}={value}")
        
        return preset


# =============================================================================
# USAGE EXAMPLES
# =============================================================================

if __name__ == '__main__':
    # Display current configuration
    ArchiveConfig.display_settings()
    
    # Validate settings
    print("\nValidation:")
    for warning in ArchiveConfig.validate_settings():
        print(warning)
    
    # Show available presets
    print("\n\nAvailable Presets:")
    print("=" * 60)
    print("1. AGGRESSIVE  - Maximum storage savings, archives after 3 days")
    print("2. BALANCED    - Recommended for most cases, archives after 7 days")
    print("3. CONSERVATIVE - Keep more data locally, archives after 30 days")
    print("=" * 60)
