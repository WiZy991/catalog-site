# Generated manually to fix merge migration issue
# This merge migration should be created on the server to replace the broken one

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        # This merge depends on both branches:
        # 1. The server branch: 0005_alter_farpostapisettings_packet_id
        # 2. The local branch: 0006_promotion (which depends on 0004)
        ('catalog', '0005_alter_farpostapisettings_packet_id'),
        ('catalog', '0006_promotion'),
    ]

    operations = [
        # Empty merge migration - just combines the two branches
    ]
