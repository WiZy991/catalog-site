import shutil
import tempfile
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from core.models import HeroCarouselSettings, HeroSlide, validate_hero_slide_image


def make_image(name='slide.png', color=(180, 0, 0)):
    buffer = BytesIO()
    Image.new('RGB', (16, 16), color).save(buffer, format='PNG')
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/png')


MEDIA_ROOT = tempfile.mkdtemp(prefix='hero-carousel-tests-')


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class HeroCarouselTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def test_homepage_keeps_logo_without_slides(self):
        response = self.client.get(reverse('core:home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'hero__logo')
        self.assertNotContains(response, 'id="heroCarousel"')

    def test_homepage_renders_active_slides_in_order_and_speed(self):
        HeroCarouselSettings.objects.create(interval_seconds=4, visible_count=2)
        HeroSlide.objects.create(image=make_image('c.png'), alt='Третий', order=30, is_active=True)
        HeroSlide.objects.create(image=make_image('a.png'), alt='Первый', order=10, is_active=True)
        HeroSlide.objects.create(image=make_image('hidden.png'), alt='Скрытый', order=5, is_active=False)
        HeroSlide.objects.create(image=make_image('b.png'), alt='Второй', order=20, is_active=True)

        response = self.client.get(reverse('core:home'))
        html = response.content.decode()

        self.assertContains(response, 'id="heroCarousel"')
        self.assertContains(response, 'data-interval="4000"')
        self.assertNotContains(response, 'hero__logo')
        self.assertLess(html.index('Первый'), html.index('Второй'))
        self.assertNotIn('Третий', html)
        self.assertNotIn('Скрытый', html)
        self.assertEqual(html.count('hero-carousel__slide'), 2)

    def test_settings_reject_speed_outside_limits(self):
        settings_obj = HeroCarouselSettings(interval_seconds=0, visible_count=0)
        with self.assertRaises(ValidationError):
            settings_obj.full_clean()

    def test_slide_rejects_oversized_or_unknown_file(self):
        class Oversized:
            size = 8 * 1024 * 1024 + 1
            name = 'banner.jpg'

        with self.assertRaises(ValidationError):
            validate_hero_slide_image(Oversized())

        slide = HeroSlide(image=make_image('notes.txt'))
        with self.assertRaises(ValidationError):
            slide.full_clean()

    def test_replacing_image_removes_previous_file(self):
        slide = HeroSlide.objects.create(image=make_image('first.png'), alt='Кадр', order=1)
        old_name = slide.image.name
        storage = slide.image.storage
        self.assertTrue(storage.exists(old_name))

        slide.image = make_image('second.png')
        slide.save()
        slide.refresh_from_db()

        self.assertNotEqual(slide.image.name, old_name)
        self.assertFalse(storage.exists(old_name))
        self.assertTrue(storage.exists(slide.image.name))
        slide.delete()
        self.assertFalse(storage.exists(slide.image.name))

    def test_admin_opens_carousel_settings_and_slide_list(self):
        user = get_user_model().objects.create_superuser('admin', 'admin@example.com', 'pass-word')
        self.client.force_login(user)

        settings_response = self.client.get(reverse('admin:core_herocarouselsettings_changelist'))
        self.assertEqual(settings_response.status_code, 302)
        change_url = reverse('admin:core_herocarouselsettings_change', args=[1])
        self.assertEqual(settings_response.url, change_url)
        change_response = self.client.get(change_url)
        self.assertContains(change_response, 'Скорость слайдшоу')
        self.assertContains(change_response, 'Количество изображений')

        slides_response = self.client.get(reverse('admin:core_heroslide_changelist'))
        self.assertEqual(slides_response.status_code, 200)
        self.assertContains(slides_response, 'Изображения карусели')
