import re
import uuid
from django.db import models
from django.conf import settings
from django.db.models import Q
from django.contrib.contenttypes.fields import GenericRelation
from model_utils import Choices
from model_utils.models import TimeStampedModel
from django.utils import timezone
from django.contrib.auth.models import User
from django.dispatch import receiver
from django.db.models.signals import post_save, pre_delete
from elecciones.models import Mesa, LugarVotacion, Eleccion
from django.contrib.contenttypes.models import ContentType
from contacto.models import DatoDeContacto
from model_utils.fields import StatusField
from model_utils import Choices


TOTAL = 'Total General'


class Fiscal(models.Model):
    TIPO_DNI = Choices('DNI', 'CI', 'LE', 'LC')
    ESTADOS = Choices('IMPORTADO', 'AUTOCONFIRMADO', 'PRE-INSCRIPTO', 'CONFIRMADO', 'DECLINADO')

    estado = StatusField(choices_name='ESTADOS', default='PRE-INSCRIPTO')
    notas = models.TextField(blank=True, help_text='Notas internas, no se muestran')
    codigo_confirmacion = models.UUIDField(default=uuid.uuid4, editable=False)
    email_confirmado = models.BooleanField(default=False)
    apellido = models.CharField(max_length=50)
    nombres = models.CharField(max_length=100)
    tipo_dni = models.CharField(choices=TIPO_DNI, max_length=3, default='DNI')
    dni = models.CharField(max_length=15, blank=True, null=True)
    datos_de_contacto = GenericRelation('contacto.DatoDeContacto', related_query_name='fiscales')
    user = models.OneToOneField('auth.User', null=True,
                    blank=True, related_name='fiscal',
                    on_delete=models.SET_NULL)


    class Meta:
        verbose_name_plural = 'Fiscales'
        unique_together = (('tipo_dni', 'dni'),)

    def agregar_dato_de_contacto(self, tipo, valor):
        type_ = ContentType.objects.get_for_model(self)
        try:
            DatoDeContacto.objects.get(content_type__pk=type_.id, object_id=self.id, tipo=tipo, valor=valor)
        except DatoDeContacto.DoesNotExist:
            DatoDeContacto.objects.create(content_object=self, tipo=tipo, valor=valor)

    @property
    def telefonos(self):
        return self.datos_de_contacto.filter(tipo='teléfono').values_list('valor', flat=True)

    @property
    def emails(self):
        return self.datos_de_contacto.filter(tipo='email').values_list('valor', flat=True)

    def __str__(self):
        return f'{self.nombres} {self.apellido}'



@receiver(post_save, sender=Fiscal)
def crear_user_para_fiscal(sender, instance=None, created=False, **kwargs):
    if not instance.user and instance.dni and instance.estado in ('AUTOCONFIRMADO', 'CONFIRMADO'):
        user = User(
            username=re.sub("[^0-9]", "", instance.dni),
            first_name=instance.nombres,
            last_name=instance.apellido,
            is_active=True,
            email=instance.emails[0] if instance.emails else ""
        )

        # user.set_password(settings.DEFAULT_PASS_PREFIX + instance.dni[-3:])
        user.save()
        instance.user = user
        instance.save(update_fields=['user'])



@receiver(pre_delete, sender=Fiscal)
def borrar_user_para_fiscal(sender, instance=None, **kwargs):
    if instance.user:
        instance.user.delete()
