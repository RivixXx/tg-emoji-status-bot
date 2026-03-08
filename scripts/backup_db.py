#!/usr/bin/env python3
"""
Supabase Backup Script
Скрипт для создания бэкапа данных из Supabase

Использование:
    python scripts/backup_db.py

Бэкап сохраняется в backup/db_backup_YYYY-MM-DD_HH-MM-SS.json
"""
import os
import sys
import json
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Добавляем корень проекта в path
sys.path.insert(0, str(Path(__file__).parent.parent))

from supabase import create_client, Client
from brains.config import SUPABASE_URL, SUPABASE_KEY

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Таблицы для бэкапа
TABLES_TO_BACKUP = [
    "memories",
    "reminders",
    "health_records",
    "aura_settings",
    "employees",
    "news_history",
    "habits",
    "work_sessions",
    "vision_history",
    "vpn_users",
    "vpn_orders",
    "vpn_referrals"
]


async def backup_table(client: Client, table_name: str, limit: int = 10000) -> dict:
    """
    Создаёт бэкап одной таблицы.
    
    Args:
        client: Supabase клиент
        table_name: Имя таблицы
        limit: Максимальное количество записей
    
    Returns:
        Словарь с данными таблицы
    """
    logger.info(f"💾 Бэкап таблицы: {table_name}")
    
    try:
        # Получаем данные с пагинацией
        all_data = []
        offset = 0
        batch_size = 1000
        
        while offset < limit:
            response = client.table(table_name).select("*").range(offset, offset + batch_size - 1).execute()
            
            if not response.data:
                break
                
            all_data.extend(response.data)
            offset += batch_size
            
            # Небольшая пауза между запросами
            await asyncio.sleep(0.1)
        
        logger.info(f"✅ {table_name}: {len(all_data)} записей")
        
        return {
            "table_name": table_name,
            "record_count": len(all_data),
            "data": all_data,
            "backed_up_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Ошибка бэкапа таблицы {table_name}: {type(e).__name__} - {e}")
        return {
            "table_name": table_name,
            "record_count": 0,
            "data": [],
            "error": str(e),
            "backed_up_at": datetime.now().isoformat()
        }


async def create_backup(output_dir: str = "backup") -> str:
    """
    Создаёт полный бэкап базы данных.
    
    Args:
        output_dir: Директория для сохранения бэкапа
    
    Returns:
        Путь к файлу бэкапа
    """
    logger.info("🚀 Начало бэкапа базы данных Supabase")
    
    # Проверяем подключение
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.error("❌ SUPABASE_URL или SUPABASE_KEY не установлены")
        return ""
    
    try:
        client = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("✅ Подключение к Supabase установлено")
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к Supabase: {e}")
        return ""
    
    # Создаем директорию для бэкапа
    backup_path = Path(output_dir)
    backup_path.mkdir(parents=True, exist_ok=True)
    
    # Бэкап каждой таблицы
    backup_data = {
        "backup_version": "1.0",
        "supabase_url": SUPABASE_URL,
        "backed_up_at": datetime.now().isoformat(),
        "tables": {}
    }
    
    total_records = 0
    
    for table_name in TABLES_TO_BACKUP:
        table_backup = await backup_table(client, table_name)
        backup_data["tables"][table_name] = table_backup
        total_records += table_backup.get("record_count", 0)
    
    # Сохраняем бэкап
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_file = backup_path / f"db_backup_{timestamp}.json"
    
    try:
        with open(backup_file, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)
        
        file_size = backup_file.stat().st_size / 1024 / 1024  # MB
        
        logger.info("=" * 60)
        logger.info(f"✅ Бэкап завершён успешно!")
        logger.info(f"📁 Файл: {backup_file}")
        logger.info(f"📊 Записей всего: {total_records}")
        logger.info(f"💾 Размер: {file_size:.2f} MB")
        logger.info("=" * 60)
        
        return str(backup_file)
        
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения бэкапа: {e}")
        return ""


async def restore_backup(backup_file: str, dry_run: bool = False) -> bool:
    """
    Восстанавливает данные из бэкапа.
    
    Args:
        backup_file: Путь к файлу бэкапа
        dry_run: Если True, только показывает что будет восстановлено
    
    Returns:
        True если успешно
    """
    logger.info(f"🔄 Восстановление из бэкапа: {backup_file}")
    
    # Проверяем файл
    backup_path = Path(backup_file)
    if not backup_path.exists():
        logger.error(f"❌ Файл бэкапа не найден: {backup_file}")
        return False
    
    try:
        with open(backup_path, "r", encoding="utf-8") as f:
            backup_data = json.load(f)
    except Exception as e:
        logger.error(f"❌ Ошибка чтения бэкапа: {e}")
        return False
    
    # Проверяем подключение
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.error("❌ SUPABASE_URL или SUPABASE_KEY не установлены")
        return False
    
    try:
        client = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("✅ Подключение к Supabase установлено")
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к Supabase: {e}")
        return False
    
    tables = backup_data.get("tables", {})
    
    for table_name, table_data in tables.items():
        records = table_data.get("data", [])
        
        if not records:
            logger.info(f"⊘ {table_name}: Нет данных для восстановления")
            continue
        
        if dry_run:
            logger.info(f"📋 {table_name}: {len(records)} записей (dry run)")
            continue
        
        logger.info(f"🔄 {table_name}: Восстановление {len(records)} записей...")
        
        # Восстанавливаем записи
        restored = 0
        errors = 0
        
        for record in records:
            try:
                # Удаляем ID чтобы создать новую запись
                record_data = {k: v for k, v in record.items() if k != "id"}
                
                response = client.table(table_name).insert(record_data).execute()
                
                if response.data:
                    restored += 1
                else:
                    errors += 1
                    
            except Exception as e:
                errors += 1
                logger.debug(f"⚠️ Ошибка восстановления записи: {e}")
        
        logger.info(f"✅ {table_name}: {restored} восстановлено, {errors} ошибок")
    
    logger.info("=" * 60)
    logger.info("✅ Восстановление завершено!")
    logger.info("=" * 60)
    
    return True


async def main():
    """Основная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Supabase Backup/Restore Utility")
    parser.add_argument("--backup", "-b", action="store_true", help="Создать бэкап")
    parser.add_argument("--restore", "-r", type=str, help="Восстановить из бэкапа")
    parser.add_argument("--dry-run", action="store_true", help="Тестовое восстановление без записи")
    parser.add_argument("--output", "-o", type=str, default="backup", help="Директория для бэкапа")
    
    args = parser.parse_args()
    
    if args.backup or (not args.restore):
        # По умолчанию создаём бэкап
        await create_backup(args.output)
    
    elif args.restore:
        # Восстановление
        await restore_backup(args.restore, dry_run=args.dry_run)


if __name__ == "__main__":
    asyncio.run(main())
