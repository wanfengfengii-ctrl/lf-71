from django.contrib import admin
from .models import (
    MaterialBatch, TensionTest, FatigueTest, DataAnomalyLog,
    MaterialProcessParam, BreakageFlowRecord, StatisticalSnapshot,
    ProcessRecipe, RecipeParam, PerformanceTarget,
    TrialPlan, TrialResult, RecipePrediction,
    RecipeComparison, OptimizationSuggestion,
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


class RecipeParamInline(admin.TabularInline):
    model = RecipeParam
    extra = 0
    fields = (
        'param_name', 'param_value', 'param_unit', 'param_type',
        'min_value', 'max_value', 'is_critical', 'description'
    )


class PerformanceTargetInline(admin.TabularInline):
    model = PerformanceTarget
    extra = 0
    fields = (
        'target_name', 'target_category', 'target_value', 'target_unit',
        'comparison_type', 'min_target', 'max_target', 'priority', 'is_mandatory'
    )


class RecipePredictionInline(admin.TabularInline):
    model = RecipePrediction
    extra = 0
    readonly_fields = (
        'predicted_durability', 'predicted_stability', 'predicted_rebound',
        'predicted_strength', 'predicted_overall', 'predicted_risk_level',
        'predicted_risk_score', 'confidence_level', 'predicted_at', 'is_latest'
    )
    fields = readonly_fields
    max_num = 5


class TrialPlanInline(admin.TabularInline):
    model = TrialPlan
    extra = 0
    fields = (
        'plan_code', 'plan_name', 'trial_type', 'status',
        'sample_count', 'planned_start_date', 'planned_end_date', 'tester'
    )
    readonly_fields = ('plan_code', 'plan_name')


class OptimizationSuggestionInline(admin.TabularInline):
    model = OptimizationSuggestion
    extra = 0
    fields = (
        'title', 'category', 'severity', 'status', 'description',
        'generated_by', 'created_at'
    )
    readonly_fields = ('created_at',)


@admin.register(ProcessRecipe)
class ProcessRecipeAdmin(admin.ModelAdmin):
    list_display = (
        'recipe_code', 'recipe_name', 'recipe_type', 'status',
        'target_bow_type', 'base_material', 'param_count', 'trial_count',
        'created_by', 'created_at'
    )
    list_filter = ('recipe_type', 'status', 'created_at')
    search_fields = ('recipe_code', 'recipe_name', 'base_material', 'description')
    inlines = [RecipeParamInline, PerformanceTargetInline, RecipePredictionInline, TrialPlanInline, OptimizationSuggestionInline]
    readonly_fields = ('created_at', 'updated_at', 'approved_at')
    fieldsets = (
        (None, {
            'fields': (
                'recipe_code', 'recipe_name', 'recipe_type', 'status',
                'target_bow_type', 'description', 'parent_recipe', 'version'
            )
        }),
        ('核心工艺参数', {
            'fields': (
                'base_material', 'twist_direction', 'twist_count', 'strand_count',
                'coating_material', 'weaving_method', 'pretreatment_process'
            )
        }),
        ('固化工艺', {
            'fields': (
                'curing_method', 'curing_temperature', 'curing_duration'
            )
        }),
        ('审批信息', {
            'fields': ('created_by', 'approved_by', 'approved_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def param_count(self, obj):
        return obj.param_count
    param_count.short_description = '参数数量'

    def trial_count(self, obj):
        return obj.trial_count
    trial_count.short_description = '试制次数'


@admin.register(RecipeParam)
class RecipeParamAdmin(admin.ModelAdmin):
    list_display = (
        'recipe', 'param_name', 'param_value', 'param_unit',
        'param_type', 'is_critical', 'tolerance_range', 'created_at'
    )
    list_filter = ('param_type', 'is_critical', 'created_at')
    search_fields = ('recipe__recipe_code', 'recipe__recipe_name', 'param_name')
    raw_id_fields = ('recipe',)
    readonly_fields = ('created_at',)

    def tolerance_range(self, obj):
        r = obj.tolerance_range
        return f'{r:.2f}' if r is not None else '-'
    tolerance_range.short_description = '容差范围'


class TrialResultInline(admin.TabularInline):
    model = TrialResult
    extra = 0
    fields = (
        'sample_id', 'test_date', 'durability_score', 'stability_score',
        'rebound_performance', 'strength_score', 'overall_score',
        'risk_level', 'result_status', 'is_broken'
    )
    readonly_fields = ('overall_score', 'result_status')


@admin.register(TrialPlan)
class TrialPlanAdmin(admin.ModelAdmin):
    list_display = (
        'plan_code', 'plan_name', 'recipe', 'trial_type', 'status',
        'material_batch', 'sample_count', 'result_count',
        'tester', 'planned_start_date', 'planned_end_date'
    )
    list_filter = ('trial_type', 'status', 'planned_start_date')
    search_fields = (
        'plan_code', 'plan_name', 'recipe__recipe_code',
        'recipe__recipe_name', 'tester'
    )
    raw_id_fields = ('recipe', 'material_batch', 'target_bow_type')
    inlines = [TrialResultInline]
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': (
                'plan_code', 'plan_name', 'recipe', 'material_batch',
                'trial_type', 'status', 'target_bow_type'
            )
        }),
        ('试制安排', {
            'fields': (
                'sample_count', 'tester', 'test_environment',
                'planned_start_date', 'planned_end_date',
                'actual_start_date', 'actual_end_date'
            )
        }),
        ('试制方案', {
            'fields': (
                'preparation_notes', 'test_procedure', 'expected_outcomes'
            ),
            'classes': ('collapse',)
        }),
        ('系统信息', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def result_count(self, obj):
        return obj.result_count
    result_count.short_description = '结果数量'


@admin.register(TrialResult)
class TrialResultAdmin(admin.ModelAdmin):
    list_display = (
        'trial_plan', 'sample_id', 'test_date', 'durability_score',
        'stability_score', 'rebound_performance', 'strength_score',
        'overall_score', 'risk_level_display', 'result_status_display',
        'is_broken', 'test_operator'
    )
    list_filter = (
        'risk_level', 'result_status', 'is_broken', 'test_date'
    )
    search_fields = (
        'trial_plan__plan_code', 'trial_plan__plan_name',
        'sample_id', 'test_operator', 'notes'
    )
    raw_id_fields = ('trial_plan',)
    readonly_fields = ('overall_score', 'result_status', 'created_at')
    fieldsets = (
        (None, {
            'fields': (
                'trial_plan', 'sample_id', 'test_date', 'test_operator'
            )
        }),
        ('性能评分', {
            'fields': (
                'durability_score', 'stability_score', 'rebound_performance',
                'strength_score', 'overall_score'
            )
        }),
        ('风险评估', {
            'fields': ('risk_level', 'risk_score')
        }),
        ('实测数据', {
            'fields': (
                'measured_force', 'measured_elongation', 'measured_rebound_rate',
                'fatigue_cycles', 'measured_diameter', 'weight_per_meter'
            )
        }),
        ('寿命预估', {
            'fields': ('lifespan_estimate_hours', 'estimated_shots'),
            'classes': ('collapse',)
        }),
        ('目标达成', {
            'fields': ('result_status', 'targets_met', 'targets_missed'),
            'classes': ('collapse',)
        }),
        ('断裂分析', {
            'fields': (
                'is_broken', 'break_location', 'break_mode', 'break_reason'
            )
        }),
        ('备注建议', {
            'fields': (
                'observations', 'issues_found', 'recommendations',
                'raw_data_reference', 'notes', 'created_at'
            )
        }),
    )

    def risk_level_display(self, obj):
        return obj.get_risk_level_display()
    risk_level_display.short_description = '风险等级'
    risk_level_display.admin_order_field = 'risk_level'

    def result_status_display(self, obj):
        return obj.get_result_status_display()
    result_status_display.short_description = '目标达成'
    result_status_display.admin_order_field = 'result_status'


@admin.register(RecipePrediction)
class RecipePredictionAdmin(admin.ModelAdmin):
    list_display = (
        'recipe', 'predicted_durability', 'predicted_stability',
        'predicted_rebound', 'predicted_strength', 'predicted_overall',
        'predicted_risk_level_display', 'confidence_level',
        'predicted_at', 'is_latest'
    )
    list_filter = ('predicted_risk_level', 'is_latest', 'predicted_at')
    search_fields = ('recipe__recipe_code', 'recipe__recipe_name')
    raw_id_fields = ('recipe',)
    readonly_fields = ('predicted_at',)

    def predicted_risk_level_display(self, obj):
        return obj.get_predicted_risk_level_display()
    predicted_risk_level_display.short_description = '风险等级'


@admin.register(RecipeComparison)
class RecipeComparisonAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'comparison_type', 'recipe_count', 'created_by', 'created_at'
    )
    list_filter = ('comparison_type', 'created_at')
    search_fields = ('name', 'created_by')
    filter_horizontal = ('recipes',)
    readonly_fields = ('created_at',)

    def recipe_count(self, obj):
        return obj.recipe_count
    recipe_count.short_description = '配方数量'


@admin.register(OptimizationSuggestion)
class OptimizationSuggestionAdmin(admin.ModelAdmin):
    list_display = (
        'recipe', 'title', 'category', 'severity_display',
        'status_display', 'generated_by', 'reviewed_by', 'created_at'
    )
    list_filter = ('category', 'severity', 'status', 'generated_by', 'created_at')
    search_fields = (
        'recipe__recipe_code', 'recipe__recipe_name',
        'title', 'description', 'suggested_action'
    )
    raw_id_fields = ('recipe', 'trial_result')
    readonly_fields = ('reviewed_at', 'created_at')
    fieldsets = (
        (None, {
            'fields': (
                'recipe', 'trial_result', 'title', 'category', 'severity', 'status'
            )
        }),
        ('建议详情', {
            'fields': (
                'description', 'current_state', 'suggested_action',
                'expected_improvement', 'affected_params'
            )
        }),
        ('审核信息', {
            'fields': (
                'reviewer_notes', 'reviewed_by', 'reviewed_at',
                'generated_by', 'created_at'
            ),
            'classes': ('collapse',)
        }),
    )

    def severity_display(self, obj):
        return obj.get_severity_display()
    severity_display.short_description = '重要程度'
    severity_display.admin_order_field = 'severity'

    def status_display(self, obj):
        return obj.get_status_display()
    status_display.short_description = '处理状态'
    status_display.admin_order_field = 'status'


@admin.register(PerformanceTarget)
class PerformanceTargetAdmin(admin.ModelAdmin):
    list_display = (
        'recipe', 'target_name', 'target_category', 'target_value',
        'target_unit', 'comparison_type', 'priority', 'is_mandatory'
    )
    list_filter = ('target_category', 'is_mandatory', 'priority')
    search_fields = ('recipe__recipe_code', 'recipe__recipe_name', 'target_name')
    raw_id_fields = ('recipe',)
    readonly_fields = ('created_at',)
