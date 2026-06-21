from django.contrib import admin
from .models import MaterialBatch, TensionTest


class TensionTestInline(admin.TabularInline):
    model = TensionTest
    extra = 0
    readonly_fields = ('rebound_rate',)
    fields = (
        'tension_force', 'elongation', 'length_before_rebound',
        'length_after_rebound', 'rebound_rate', 'is_broken',
        'abnormal_break', 'break_reason', 'test_time', 'notes'
    )


@admin.register(MaterialBatch)
class MaterialBatchAdmin(admin.ModelAdmin):
    list_display = (
        'batch_number', 'material_source', 'diameter',
        'initial_length', 'test_count', 'is_broken', 'created_at'
    )
    search_fields = ('batch_number', 'material_source')
    list_filter = ('created_at',)
    inlines = [TensionTestInline]
    readonly_fields = ('created_at',)


@admin.register(TensionTest)
class TensionTestAdmin(admin.ModelAdmin):
    list_display = (
        'batch', 'tension_force', 'elongation', 'rebound_rate',
        'is_broken', 'abnormal_break', 'test_time'
    )
    list_filter = ('is_broken', 'abnormal_break', 'test_time')
    search_fields = ('batch__batch_number', 'break_reason', 'notes')
    readonly_fields = ('rebound_rate',)
    raw_id_fields = ('batch',)
