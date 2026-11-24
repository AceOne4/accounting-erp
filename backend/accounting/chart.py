"""Default chart of accounts for a new company (ported from the old seed scripts,
with the treasury boxes and cash difference account already applied)."""
from .models import Account

A, L, E, R, X = "asset", "liability", "equity", "revenue", "expense"

# (code, Arabic name, English name, type, parent code, is_leaf, requires_partner)
# Every parent is listed before its children.
DEFAULT_CHART = [
    ("1", "الأصول", "Assets", A, None, False, False),
    ("10", "الأصول المتداولة", "Current assets", A, "1", False, False),
    ("101", "الخزينة (النقدية)", "Treasury (cash)", A, "10", False, False),
    ("1011", "خزنة المصروفات", "Expenses box", A, "101", True, False),
    ("1012", "خزنة التحصيلات", "Collections box", A, "101", True, False),
    ("102", "العملاء", "Customers (receivables)", A, "10", True, True),
    ("103", "البنوك", "Banks", A, "10", True, False),
    ("104", "أوراق القبض", "Notes receivable", A, "10", True, True),
    ("105", "المخزون", "Inventory", A, "10", True, False),
    ("106", "ضريبة القيمة المضافة (مدخلات)", "VAT input", A, "10", True, False),
    ("107", "سلف وعهد العاملين", "Employee advances", A, "10", True, False),
    ("108", "مصروفات مدفوعة مقدمًا", "Prepaid expenses", A, "10", True, False),
    ("109", "مدينون متنوعون", "Other receivables", A, "10", True, False),
    ("11", "الأصول الثابتة", "Fixed assets", A, "1", False, False),
    ("111", "الأراضي", "Land", A, "11", True, False),
    ("112", "المباني", "Buildings", A, "11", True, False),
    ("113", "الآلات والمعدات", "Machinery and equipment", A, "11", True, False),
    ("114", "وسائل النقل", "Vehicles", A, "11", True, False),
    ("115", "الأثاث والتجهيزات", "Furniture and fixtures", A, "11", True, False),
    ("116", "أجهزة الحاسب", "Computers and equipment", A, "11", True, False),
    ("119", "مجمع الإهلاك", "Accumulated depreciation", A, "11", True, False),
    ("2", "الالتزامات", "Liabilities", L, None, False, False),
    ("20", "الالتزامات المتداولة", "Current liabilities", L, "2", False, False),
    ("201", "الموردين", "Suppliers (payables)", L, "20", True, True),
    ("202", "أوراق الدفع", "Notes payable", L, "20", True, True),
    ("203", "ضريبة القيمة المضافة (مخرجات)", "VAT output", L, "20", True, False),
    ("204", "مصروفات مستحقة", "Accrued expenses", L, "20", True, False),
    ("205", "إيرادات مقدمة", "Deferred revenue", L, "20", True, False),
    ("206", "ضريبة الدخل المستحقة", "Income tax payable", L, "20", True, False),
    ("207", "ضريبة كسب العمل المستحقة", "Payroll tax payable", L, "20", True, False),
    ("208", "التأمينات الاجتماعية المستحقة", "Social insurance payable", L, "20", True, False),
    ("209", "دائنون متنوعون", "Other payables", L, "20", True, False),
    ("21", "الالتزامات طويلة الأجل", "Long-term liabilities", L, "2", False, False),
    ("210", "بضاعة مستلمة لم تُفوتر", "Goods received not invoiced", L, "20", True, True),
    ("211", "قروض طويلة الأجل", "Long-term loans", L, "21", True, False),
    ("3", "حقوق الملكية", "Equity", E, None, False, False),
    ("301", "رأس المال", "Share capital", E, "3", True, False),
    ("302", "الاحتياطيات", "Reserves", E, "3", True, False),
    ("303", "الأرباح (الخسائر) المرحّلة", "Retained earnings", E, "3", True, False),
    ("304", "جاري الشركاء", "Partners' current account", E, "3", True, False),
    ("305", "أرباح (خسائر) العام", "Current year profit (loss)", E, "3", True, False),
    ("4", "الإيرادات", "Revenue", R, None, False, False),
    ("401", "المبيعات", "Sales", R, "4", True, False),
    ("402", "مردودات ومسموحات المبيعات", "Sales returns and allowances", R, "4", True, False),
    ("403", "إيرادات الخدمات", "Service revenue", R, "4", True, False),
    ("404", "إيرادات أخرى", "Other income", R, "4", True, False),
    ("405", "فوائد دائنة", "Interest income", R, "4", True, False),
    ("5", "المصروفات", "Expenses", X, None, False, False),
    ("50", "تكلفة المبيعات", "Cost of sales", X, "5", False, False),
    ("501", "تكلفة البضاعة المباعة", "Cost of goods sold", X, "50", True, False),
    ("502", "المشتريات", "Purchases", X, "50", True, False),
    ("503", "مردودات المشتريات", "Purchase returns", X, "50", True, False),
    ("504", "مصاريف شحنة", "Freight and shipping expenses", X, "50", True, False),
    ("505", "تكلفة بضاعة فري", "Cost of free goods", X, "50", True, False),
    ("51", "المصروفات الإدارية والعمومية", "General and administrative expenses", X, "5", False, False),
    ("510", "عجز وزيادة الخزينة", "Cash shortage and overage", X, "51", True, False),
    ("511", "الرواتب والأجور", "Salaries and wages", X, "51", True, False),
    ("512", "الإيجارات", "Rent", X, "51", True, False),
    ("513", "الكهرباء والمياه والغاز", "Utilities", X, "51", True, False),
    ("514", "الاتصالات والإنترنت", "Communications and internet", X, "51", True, False),
    ("515", "الصيانة والإصلاح", "Repairs and maintenance", X, "51", True, False),
    ("516", "الأتعاب المهنية", "Professional fees", X, "51", True, False),
    ("517", "مصروف الإهلاك", "Depreciation expense", X, "51", True, False),
    ("518", "ضرائب ورسوم", "Taxes and fees", X, "51", True, False),
    ("519", "مصروفات إدارية أخرى", "Other administrative expenses", X, "51", True, False),
    ("52", "مصروفات البيع والتسويق", "Selling and marketing expenses", X, "5", False, False),
    ("521", "الدعاية والإعلان", "Advertising", X, "52", True, False),
    ("522", "عمولات المبيعات", "Sales commissions", X, "52", True, False),
    ("523", "الشحن والتوصيل", "Shipping and delivery", X, "52", True, False),
    ("53", "المصروفات التمويلية", "Finance costs", X, "5", False, False),
    ("531", "الفوائد البنكية", "Bank interest", X, "53", True, False),
    ("532", "المصروفات البنكية", "Bank charges", X, "53", True, False),
    ("533", "فروق العملة", "Foreign exchange differences", X, "53", True, False),
]


def seed_default_chart(company):
    """Create or update the default chart for a company. Safe to run again.

    Returns (created, updated).
    """
    created = updated = 0
    by_code = {a.code: a for a in Account.objects.filter(company=company)}
    for code, name, name_en, acc_type, parent_code, is_leaf, requires_partner in DEFAULT_CHART:
        account, was_created = Account.objects.update_or_create(
            company=company,
            code=code,
            defaults={
                "name": name,
                "name_en": name_en,
                "type": acc_type,
                "parent": by_code[parent_code] if parent_code else None,
                "is_leaf": is_leaf,
                "requires_partner": requires_partner,
            },
        )
        by_code[code] = account
        created += was_created
        updated += not was_created
    return created, updated
