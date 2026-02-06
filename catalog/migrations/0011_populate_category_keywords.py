# Generated manually - populate keywords for existing categories

from django.db import migrations


# Ключевые слова для основных категорий (из services.py)
CATEGORY_KEYWORDS = {
    'Автоэлектрика': 'стартер, генератор, датчик, реле, проводка, блок управления, катушка зажигания, свеча, свеча накала, свеча зажигания, аккумулятор, предохранитель, лампа, фара, фонарь, сигнал, электро, sensor, starter, generator, alternator, coil, ignition, высоковольтн, провод, spark plug, glow plug',
    'Двигатель и выхлопная система': 'двигатель, мотор, поршень, кольца поршневые, коленвал, распредвал, клапан, прокладка гбц, гбц, блок цилиндров, турбина, турбокомпрессор, форсунка, тнвд, насос топливный, фильтр, масляный насос, помпа, водяной насос, термостат, радиатор, вентилятор, вискомуфта, ремень грм, цепь грм, натяжитель, ролик, выхлоп, глушитель, катализатор, коллектор, engine, piston, valve, turbo, injector, вкладыш, шатун, маслосъемн, сальник, маслоохладитель, интеркулер, egr, дроссель, впуск, плунжер, трубк, обратк, топливн, ремкомплект грм, ремкомплект двигателя, отопител, автономн, печк, прокладка, ремень, oil seal',
    'Детали подвески': 'амортизатор, пружина, рычаг, сайлентблок, шаровая, опора, стойка, втулка стабилизатора, стабилизатор, подшипник ступицы, ступица, кулак, цапфа, тяга, наконечник, пыльник, отбойник, suspension, shock, spring, arm, bushing, bearing, hub, подвеск',
    'Трансмиссия и тормозная система': 'кпп, коробка передач, акпп, мкпп, сцепление, корзина сцепления, диск сцепления, выжимной, маховик, редуктор, дифференциал, полуось, шрус, кардан, крестовина, раздатка, раздаточная, тормоз, колодки, диск тормозной, суппорт, цилиндр тормозной, шланг тормозной, abs, transmission, clutch, brake, gearbox, трансмисс, привод',
}


def populate_keywords(apps, schema_editor):
    """Заполняет ключевые слова для существующих категорий."""
    Category = apps.get_model('catalog', 'Category')
    
    for cat_name, keywords in CATEGORY_KEYWORDS.items():
        # Обновляем только корневые категории (без родителя)
        Category.objects.filter(
            name=cat_name,
            parent__isnull=True
        ).update(keywords=keywords)


def reverse_keywords(apps, schema_editor):
    """Очищает ключевые слова."""
    Category = apps.get_model('catalog', 'Category')
    Category.objects.filter(
        name__in=CATEGORY_KEYWORDS.keys()
    ).update(keywords='')


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0010_category_keywords'),
    ]

    operations = [
        migrations.RunPython(populate_keywords, reverse_keywords),
    ]
