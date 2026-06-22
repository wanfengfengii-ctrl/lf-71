from django.contrib import admin
from .models import (
    MaterialBatch, TensionTest, FatigueTest, DataAnomalyLog,
    MaterialProcessParam, BreakageFlowRecord, StatisticalSnapshot,
)


class TensionTestInline(admin.TabularInline):
    model = TensionTest
    extra = 0
    readonly_fields = ('rebound_rate', 'stress', 'strain')
    fields = (
        'tension_force', 'elongation', 'length_before_rebound',
        'length_after_rebound', 'rebound_rate', 'stress', 'strain',
        'is_broken', 'abnormal_break', 'break_reason', 'is_flagged',
        'flag_reason', 'test_time', 'notes'
    )


class FatigueTestInline(admin.TabularInline):
    model = FatigueTest
    extra = 0
    readonly_fields = ('stress_amplitude', 'mean_stress', 'damage_severity')
    fields = (
        'load_force', 'cycle_count', 'frequency', 'load_ratio',
        'stress_amplitude', 'mean_stress', 'damage_severity',
        'result', 'elongation_after', 'is_flagged', 'flag_reason',
        'test_time', 'notes'
    )


class ProcessParamInline(admin.TabularInline):
    model = MaterialProcessParam
    extra = 0
    fields = (
        'param_name', 'param_value', 'param_unit', 'param_type', 'description'
    )


class FlowRecordInline(admin.TabularInline):
    model = BreakageFlowRecord
    extra = 0
    readonly_fields = ('created_at',)
    fields = (
        'action', 'operator', 'notes', 'source_test_id',
        'source_test_type', 'created_at'
    )


@admin.register(MaterialBatch)
class MaterialBatchAdmin(admin.ModelAdmin):
    list_display = (
        'batch_number', 'material_source', 'diameter',
        'initial_length', 'status', 'test_count', 'fatigue_test_count_display',
        'anomaly_count_display', 'created_at'
    )
    list_filter = ('status', 'created_at')
    search_fields = ('batch_number', 'material_source')
    inlines = [TensionTestInline, FatigueTestInline, ProcessParamInline, FlowRecordInline]
    readonly_fields = (
        'created_at', 'broken_at', 'reviewed_at',
        'youngs_modulus_display', 'tensile_strength_display',
        'elongation_at_break_display', 'avg_rebound_rate_display',
    )
    fieldsets = (
        (None, {
            'fields': (
                'batch_number', 'material_source', 'diameter',
                'initial_length', 'description', 'status'
            )
        }),
        ('状态信息', {
            'fields': (
                'broken_at', 'reviewed_at', 'review_notes', 'created_at'
            ),
            'classes': ('collapse',)
        }),
        ('派生指标', {
            'fields': (
                'youngs_modulus_display', 'tensile_strength_display',
                'elongation_at_break_display', 'avg_rebound_rate_display',
            ),
            'classes': ('collapse',)
        }),
    )

    def anomaly_count_display(self, obj):
        return obj.anomaly_count
    anomaly_count_display.short_description = '未处理异常'

    def fatigue_test_count_display(self, obj):
        return obj.fatigue_test_count
    fatigue_test_count_display.short_description = '疲劳测试数'

    def youngs_modulus_display(self, obj):
        return f'{obj.youngs_modulus} MPa' if obj.youngs_modulus else '-'
    youngs_modulus_display.short_description = '杨氏模量'

    def tensile_strength_display(self, obj):
        return f'{obj.tensile_strength} MPa' if obj.tensile_strength else '-'
    tensile_strength_display.short_description = '拉伸强度'

    def elongation_at_break_display(self, obj):
        return f'{obj.elongation_at_break}%' if obj.elongation_at_break else '-'
    elongation_at_break_display.short_description = '断裂伸长率'

    def avg_rebound_rate_display(self, obj):
        return f'{obj.avg_rebound_rate}%' if obj.avg_rebound_rate else '-'
    avg_rebound_rate_display.short_description = '平均回弹率'


@admin.register(TensionTest)
class TensionTestAdmin(admin.ModelAdmin):
    list_display = (
        'batch', 'tension_force', 'elongation', 'rebound_rate',
        'stress', 'strain', 'is_broken', 'abnormal_break',
        'is_flagged', 'test_time'
    )
    list_filter = ('is_broken', 'abnormal_break', 'is_flagged', 'test_time')
    search_fields = ('batch__batch_number', 'break_reason', 'notes')
    readonly_fields = ('rebound_rate', 'stress', 'strain')
    raw_id_fields = ('batch',)


@admin.register(FatigueTest)
class FatigueTestAdmin(admin.ModelAdmin):
    list_display = (
        'batch', 'load_force', 'cycle_count', 'frequency',
        'stress_amplitude', 'result', 'is_flagged', 'test_time'
    )
    list_filter = ('result', 'is_flagged', 'test_time')
    search_fields = ('batch__batch_number', 'notes')
    readonly_fields = ('stress_amplitude', 'mean_stress', 'damage_severity')
    raw_id_fields = ('batch',)


@admin.register(DataAnomalyLog)
class DataAnomalyLogAdmin(admin.ModelAdmin):
    list_display = (
        'batch', 'source_type', 'severity', 'anomaly_description',
        'is_resolved', 'created_at'
    )
    list_filter = ('source_type', 'severity', 'is_resolved', 'created_at')
    search_fields = ('batch__batch_number', 'anomaly_description')
    raw_id_fields = ('batch',)


@admin.register(MaterialProcessParam)
class MaterialProcessParamAdmin(admin.ModelAdmin):
    list_display = (
        'batch', 'param_name', 'param_value', 'param_unit',
        'param_type', 'created_at'
    )
    list_filter = ('param_type', 'created_at')
    search_fields = ('batch__batch_number', 'param_name')
    raw_id_fields = ('batch',)


@admin.register(BreakageFlowRecord)
class BreakageFlowRecordAdmin(admin.ModelAdmin):
    list_display = (
        'batch', 'action', 'operator', 'created_at'
    )
    list_filter = ('action', 'created_at')
    search_fields = ('batch__batch_number', 'operator', 'notes')
    raw_id_fields = ('batch',)
    readonly_fields = ('created_at',)


@admin.register(StatisticalSnapshot)
class StatisticalSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        'snapshot_date', 'snapshot_type', 'total_batches',
        'total_tension_tests', 'total_fatigue_tests', 'created_at'
    )
    list_filter = ('snapshot_type', 'snapshot_date')
    readonly_fields = ('created_at',)
