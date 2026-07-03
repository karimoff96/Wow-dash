#!/usr/bin/env python
"""Add missing Russian translations for common UI strings."""
import polib

# Dictionary of English -> Russian translations for sidebar and common UI elements
TRANSLATIONS = {
    # Billing & Subscriptions section
    "Billing & Subscriptions": "Биллинг и подписки",
    "Centers Monitoring": "Мониторинг центров",
    "All Centers": "Все центры",
    "Subscriptions": "Подписки",
    "Tariff Plans": "Тарифные планы",
    "Usage Tracking": "Отслеживание использования",
    "Contact Requests": "Запросы на контакт",
    
    # Renewal page
    "Renew Subscription": "Продлить подписку",
    "Current Subscription": "Текущая подписка",
    "Renewal Options": "Варианты продления",
    "Select Tariff & Duration": "Выберите тариф и срок",
    "Choose tariff plan...": "Выберите тарифный план...",
    "Select Pricing Duration": "Выберите продолжительность",
    "Select tariff first...": "Сначала выберите тариф...",
    "Choose duration...": "Выберите продолжительность...",
    "The subscription will be extended from current end date by selected duration": "Подписка будет продлена с текущей даты окончания на выбранный срок",
    "New End Date": "Новая дата окончания",
    "Payment Information": "Информация об оплате",
    "Amount Paid": "Сумма оплаты",
    "Leave empty if payment not yet received": "Оставьте пустым, если оплата еще не получена",
    "Payment Method": "Способ оплаты",
    "Not specified": "Не указано",
    "Cash": "Наличные",
    "Bank Transfer": "Банковский перевод",
    "Transaction ID": "ID транзакции",
    "Optional": "Необязательно",
    "Notes": "Примечания",
    "Optional notes about this renewal...": "Необязательные примечания об этом продлении...",
    "Renewing will extend the subscription period. Status will be set to 'Pending' until payment is confirmed.": "Продление увеличит срок подписки. Статус будет установлен как 'Ожидание' до подтверждения оплаты.",
    "Cancel": "Отмена",
    "Available Tariffs": "Доступные тарифы",
    "Pricing": "Стоимость",
    
    # Subscription detail page
    "Subscription Detail": "Детали подписки",
    "Convert to Paid Subscription": "Преобразовать в платную подписку",
    "Renew Subscription": "Продлить подписку",
    "Back to List": "Вернуться к списку",
    "Center Analytics Summary": "Сводка аналитики центра",
    "View Full Analytics": "Посмотреть полную аналитику",
    "Account Age": "Возраст аккаунта",
    "years": "лет",
    "days": "дней",
    "Lifetime Value": "Пожизненная ценность",
    "Total Subscriptions": "Всего подписок",
    "First Subscription": "Первая подписка",
    "Subscription Information": "Информация о подписке",
    "Organization": "Организация",
    "Tariff Plan": "Тарифный план",
    "Duration": "Продолжительность",
    "month(s)": "месяц(ев)",
    "Status": "Статус",
    "Free Trial": "Пробная версия",
    "Active": "Активна",
    "Expired": "Истекла",
    "Pending": "Ожидание",
    "Cancelled": "Отменена",
    "Trial End Date": "Дата окончания пробной версии",
    "Trial Days Remaining": "Осталось дней пробной версии",
    "Start Date": "Дата начала",
    "End Date": "Дата окончания",
    "Days Remaining": "Осталось дней",
    "Auto-Renew": "Автопродление",
    "Yes": "Да",
    "No": "Нет",
    "Update Status": "Обновить статус",
    "Plan Features": "Возможности плана",
    "Features": "Возможности",
    "Orders": "Заказы",
    "Analytics": "Аналитика",
    "Integration": "Интеграция",
    "Marketing": "Маркетинг",
    "Storage": "Хранилище",
    "Financial": "Финансы",
    "Support": "Поддержка",
    "Advanced": "Расширенные",
    "Services": "Услуги",
    "No features available in this plan": "В этом плане нет доступных функций",
    "Upgrade Plan": "Улучшить план",
    "Current Usage": "Текущее использование",
    "Branches": "Филиалы",
    "Staff": "Сотрудники",
    "Orders (This Month)": "Заказы (этот месяц)",
    "Recent History": "Недавняя история",
    "entries": "записей",
    "View Complete History": "Посмотреть полную историю",
    "No history available": "История недоступна",
    
    # Common sidebar items
    "Superuser Tools": "Инструменты суперпользователя",
    "Dashboard": "Панель управления",
    "My Branch": "Мой филиал",
    "Customers": "Клиенты",
    "Bulk Payment & Top Up": "Массовый платеж и пополнение",
    "Categories": "Категории",
    "Products": "Товары",
    "Expenses": "Расходы",
    "Languages": "Языки",
    "Analytics & Reports": "Аналитика и отчеты",
    "My Statistics": "Моя статистика",
    "Dashboards": "Дашборды",
    "Sales Overview": "Обзор продаж",
    "Finance & Payments": "Финансы и платежи",
    "Reports": "Отчеты",
    "Financial Reports": "Финансовые отчеты",
    "Unit Economy": "Юнит-экономика",
    "Debtors Report": "Отчет о должниках",
    "Payment History": "История платежей",
    "Expense Analytics": "Аналитика расходов",
    "Order Reports": "Отчеты по заказам",
    "Staff Performance": "Эффективность сотрудников",
    "Branch Comparison": "Сравнение филиалов",
    "Customer Analytics": "Аналитика клиентов",
    "Audit Logs": "Журналы аудита",
}

def add_translations():
    """Add missing translations to Russian .po file."""
    po_file = 'locale/ru/LC_MESSAGES/django.po'
    
    try:
        po = polib.pofile(po_file)
        
        added = 0
        updated = 0
        
        for english, russian in TRANSLATIONS.items():
            # Check if entry exists
            entry = po.find(english)
            
            if entry:
                # Update if not translated or different
                if not entry.msgstr or entry.msgstr != russian:
                    entry.msgstr = russian
                    updated += 1
                    print(f"✓ Updated: {english} -> {russian}")
            else:
                # Add new entry
                new_entry = polib.POEntry(
                    msgid=english,
                    msgstr=russian,
                )
                po.append(new_entry)
                added += 1
                print(f"+ Added: {english} -> {russian}")
        
        # Save the file
        po.save(po_file)
        
        print(f"\n{'='*50}")
        print(f"Added: {added} translations")
        print(f"Updated: {updated} translations")
        print(f"{'='*50}")
        
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == '__main__':
    if add_translations():
        print("\nNow run: python compile_messages_manual.py")
    else:
        print("\nFailed to add translations")
