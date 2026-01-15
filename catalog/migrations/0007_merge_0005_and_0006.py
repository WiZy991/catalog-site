# Generated manually to merge migration branches
# This replaces the broken 0006_merge_20260115_1248.py

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        # Merge depends on both branches:
        # 1. Server branch: 0005_alter_farpostapisettings_packet_id (exists on server)
        # 2. Local branch: 0006_promotion (exists locally, depends on 0004)
        ('catalog', '0005_alter_farpostapisettings_packet_id'),
        ('catalog', '0006_promotion'),
    ]

    operations = [
        # Empty merge migration - just combines the two branches
    ]
