import json
import math

from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView
)
from django.contrib import messages

from .models import (
    MaterialBatch, TensionTest, FatigueTest, DataAnomalyLog,
    MaterialProcessParam, BreakageFlowRecord, StatisticalSnapshot,
)
from .forms import (
    MaterialBatchForm, TensionTestForm, FatigueTestForm,
    BatchReviewForm, AnomalyResolveForm, MaterialProcessParamForm,
    ProcessNoteForm,
)
from .utils import (
    AnomalyDetector, StatisticsAnalyzer, ReboundRateCalculator,
    BreakFlowManager, SnapshotGenerator,
)


class DashboardView(View):
    def get(self, request):
        analyzer = StatisticsAnalyzer()
        global_stats = analyzer.get_global_statistics()

        batches = MaterialBatch.objects.all()
        total_batches = batches.count()
        broken_batches = sum(1 for b in batches if b.is_broken)
        active_batches = total_batches - broken_batches
        total_tension_tests = TensionTest.objects.count()
        total_fatigue_tests = FatigueTest.objects.count()
        total_tests = total_tension_tests + total_fatigue_tests
        unresolved_anomalies = DataAnomalyLog.objects.filter(is_resolved=False).count()
        flagged_tension = TensionTest.objects.filter(is_flagged=True).count()
        flagged_fatigue = FatigueTest.objects.filter(is_flagged=True).count()
        review_batches = batches.filter(status=MaterialBatch.STATUS_REVIEW).count()
        recent_batches = batches[:5]
        recent_tests = TensionTest.objects.all()[:8]
        recent_fatigue_tests = FatigueTest.objects.all()[:8]
        recent_anomalies = DataAnomalyLog.objects.filter(is_resolved=False)[:5]
        recent_flow_records = BreakageFlowRecord.objects.all()[:10]

        status_distribution = {}
        for choice_val, choice_label in MaterialBatch.STATUS_CHOICES:
            status_distribution[choice_val] = {
                'label': choice_label,
                'count': batches.filter(status=choice_val).count()
            }

        context = {
            'total_batches': total_batches,
            'broken_batches': broken_batches,
            'active_batches': active_batches,
            'total_tests': total_tests,
            'total_tension_tests': total_tension_tests,
            'total_fatigue_tests': total_fatigue_tests,
            'unresolved_anomalies': unresolved_anomalies,
            'flagged_data_count': flagged_tension + flagged_fatigue,
            'review_batches': review_batches,
            'recent_batches': recent_batches,
            'recent_tests': recent_tests,
            'recent_fatigue_tests': recent_fatigue_tests,
            'recent_anomalies': recent_anomalies,
            'recent_flow_records': recent_flow_records,
            'status_distribution_json': json.dumps(status_distribution, ensure_ascii=False),
            'trend_data_json': json.dumps(global_stats.get('trend', []), ensure_ascii=False),
            'source_distribution_json': json.dumps(
                global_stats.get('source_distribution', []), ensure_ascii=False
            ),
            'global_summary': global_stats.get('summary', {}),
        }
        return render(request, 'materials/dashboard.html', context)


class MaterialBatchListView(ListView):
    model = MaterialBatch
    template_name = 'materials/batch_list.html'
    context_object_name = 'batches'
    paginate_by = 20

    def get_queryset(self):
        queryset = MaterialBatch.objects.all()
        q = self.request.GET.get('q')
        if q:
            queryset = queryset.filter(
                batch_number__icontains=q
            ) | queryset.filter(
                material_source__icontains=q
            )
        status_filter = self.request.GET.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        context['status_filter'] = self.request.GET.get('status', '')
        context['status_choices'] = MaterialBatch.STATUS_CHOICES
        return context


class MaterialBatchDetailView(DetailView):
    model = MaterialBatch
    template_name = 'materials/batch_detail.html'
    context_object_name = 'batch'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tests = self.object.tension_tests.order_by('test_time')
        fatigue_tests = self.object.fatigue_tests.order_by('test_time')
        context['tests'] = tests
        context['fatigue_tests'] = fatigue_tests
        context['anomaly_logs'] = self.object.anomaly_logs.order_by('-created_at')
        context['flow_records'] = self.object.flow_records.order_by('-created_at')
        context['process_params'] = self.object.process_params.order_by('param_type', 'param_name')

        analyzer = StatisticsAnalyzer()
        context['comprehensive_stats'] = analyzer.get_batch_comprehensive_stats(self.object)
        context['batch_stats_summary'] = self.object.get_statistics_summary()

        chart_data = []
        for test in tests:
            chart_data.append({
                'x': float(test.elongation),
                'y': float(test.tension_force),
                'broken': test.is_broken,
                'flagged': test.is_flagged,
                'time': test.test_time.strftime('%Y-%m-%d %H:%M'),
                'stress': test.stress,
                'strain': test.strain,
            })
        context['chart_data_json'] = json.dumps(chart_data, ensure_ascii=False)

        stress_strain_data = []
        for test in tests:
            if test.stress is not None and test.strain is not None:
                stress_strain_data.append({
                    'x': float(test.strain),
                    'y': float(test.stress),
                    'broken': test.is_broken,
                    'flagged': test.is_flagged,
                })
        context['stress_strain_json'] = json.dumps(stress_strain_data, ensure_ascii=False)

        fatigue_chart_data = []
        for ft in fatigue_tests:
            fatigue_chart_data.append({
                'x': ft.cycle_count,
                'y': float(ft.load_force),
                'result': ft.result,
                'flagged': ft.is_flagged,
                'time': ft.test_time.strftime('%Y-%m-%d %H:%M'),
                'damage_severity': ft.damage_severity,
            })
        context['fatigue_chart_data_json'] = json.dumps(fatigue_chart_data, ensure_ascii=False)

        rebound_chart_data = []
        rebound_tests = tests.filter(rebound_rate__isnull=False).order_by('test_time')
        for idx, test in enumerate(rebound_tests):
            rebound_chart_data.append({
                'x': idx + 1,
                'y': float(test.rebound_rate),
                'force': float(test.tension_force),
            })
        context['rebound_chart_json'] = json.dumps(rebound_chart_data, ensure_ascii=False)

        return context


class MaterialBatchCreateView(CreateView):
    model = MaterialBatch
    form_class = MaterialBatchForm
    template_name = 'materials/batch_form.html'

    def get_success_url(self):
        messages.success(self.request, '材料批次创建成功')
        return reverse('materials:batch_detail', kwargs={'pk': self.object.pk})


class MaterialBatchUpdateView(UpdateView):
    model = MaterialBatch
    form_class = MaterialBatchForm
    template_name = 'materials/batch_form.html'

    def get_success_url(self):
        messages.success(self.request, '材料批次更新成功')
        return reverse('materials:batch_detail', kwargs={'pk': self.object.pk})


class MaterialBatchDeleteView(DeleteView):
    model = MaterialBatch
    template_name = 'materials/batch_confirm_delete.html'

    def get_success_url(self):
        messages.success(self.request, '材料批次已删除')
        return reverse('materials:batch_list')


class BatchReviewView(View):
    def get(self, request, pk):
        batch = get_object_or_404(MaterialBatch, pk=pk)
        if batch.status not in (MaterialBatch.STATUS_BROKEN, MaterialBatch.STATUS_REVIEW):
            messages.warning(request, '该批次不在审核状态')
            return redirect('materials:batch_detail', pk=batch.pk)
        if batch.status == MaterialBatch.STATUS_BROKEN:
            BreakFlowManager.start_review(batch)
        form = BatchReviewForm()
        context = {
            'batch': batch,
            'form': form,
            'flow_records': batch.flow_records.order_by('-created_at'),
            'breaking_tests': batch.tension_tests.filter(is_broken=True),
            'breaking_fatigue_tests': batch.fatigue_tests.filter(result=FatigueTest.RESULT_BROKEN),
        }
        return render(request, 'materials/batch_review.html', context)

    def post(self, request, pk):
        batch = get_object_or_404(MaterialBatch, pk=pk)
        form = BatchReviewForm(request.POST)
        if form.is_valid():
            action = form.cleaned_data['action']
            review_notes = form.cleaned_data.get('review_notes', '')
            if action == 'archive':
                success, msg = BreakFlowManager.archive_batch(batch, review_notes=review_notes)
                if success:
                    messages.success(request, msg)
                else:
                    messages.error(request, msg)
            elif action == 'reactivate':
                success, msg = BreakFlowManager.reactivate_batch(batch, review_notes=review_notes)
                if success:
                    messages.success(request, msg)
                else:
                    messages.error(request, msg)
            return redirect('materials:batch_detail', pk=batch.pk)
        context = {
            'batch': batch,
            'form': form,
            'flow_records': batch.flow_records.order_by('-created_at'),
        }
        return render(request, 'materials/batch_review.html', context)


class BatchFlowNoteView(View):
    def get(self, request, pk):
        batch = get_object_or_404(MaterialBatch, pk=pk)
        form = ProcessNoteForm()
        context = {
            'batch': batch,
            'form': form,
        }
        return render(request, 'materials/batch_flow_note.html', context)

    def post(self, request, pk):
        batch = get_object_or_404(MaterialBatch, pk=pk)
        form = ProcessNoteForm(request.POST)
        if form.is_valid():
            notes = form.cleaned_data['notes']
            operator = form.cleaned_data.get('operator', '')
            batch.record_flow_action(
                action=BreakageFlowRecord.ACTION_NOTE_ADDED,
                notes=notes,
                operator=operator,
            )
            messages.success(request, '流程备注已添加')
            return redirect('materials:batch_detail', pk=batch.pk)
        context = {
            'batch': batch,
            'form': form,
        }
        return render(request, 'materials/batch_flow_note.html', context)


class TensionTestCreateView(CreateView):
    model = TensionTest
    form_class = TensionTestForm
    template_name = 'materials/test_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.batch = get_object_or_404(MaterialBatch, pk=kwargs['batch_pk'])
        if not self.batch.can_add_test():
            messages.error(request, '该批次样本已断裂或处于审核/归档状态，无法新增测试记录')
            return redirect('materials:batch_detail', pk=self.batch.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['batch'] = self.batch
        existing_tests = self.batch.tension_tests.filter(is_flagged=False)
        if existing_tests.exists():
            forces = list(existing_tests.values_list('tension_force', flat=True))
            elongations = list(existing_tests.values_list('elongation', flat=True))
            context['reference_stats'] = {
                'avg_force': round(sum(forces) / len(forces), 2),
                'min_force': min(forces),
                'max_force': max(forces),
                'avg_elongation': round(sum(elongations) / len(elongations), 2),
                'min_elongation': min(elongations),
                'max_elongation': max(elongations),
                'test_count': existing_tests.count(),
            }
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['batch'] = self.batch
        return kwargs

    def form_valid(self, form):
        form.instance.batch = self.batch
        response = super().form_valid(form)
        self._check_and_create_anomaly(form.instance)
        return response

    def _check_and_create_anomaly(self, test):
        detector = AnomalyDetector(test.batch)
        anomalies = detector.check_tension_test(test, exclude_pk=test.pk)
        if anomalies:
            detector.create_anomaly_logs(
                anomalies, DataAnomalyLog.SOURCE_TENSION, test.pk
            )

    def get_success_url(self):
        messages.success(self.request, '测试记录添加成功')
        return reverse('materials:batch_detail', kwargs={'pk': self.batch.pk})


class TensionTestUpdateView(UpdateView):
    model = TensionTest
    form_class = TensionTestForm
    template_name = 'materials/test_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['batch'] = self.object.batch
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['batch'] = self.object.batch
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        detector = AnomalyDetector(self.object.batch)
        anomalies = detector.check_tension_test(self.object, exclude_pk=self.object.pk)
        if anomalies:
            detector.create_anomaly_logs(
                anomalies, DataAnomalyLog.SOURCE_TENSION, self.object.pk
            )
        return response

    def get_success_url(self):
        messages.success(self.request, '测试记录更新成功')
        return reverse('materials:batch_detail', kwargs={'pk': self.object.batch.pk})


class TensionTestDeleteView(DeleteView):
    model = TensionTest
    template_name = 'materials/test_confirm_delete.html'

    def get_success_url(self):
        messages.success(self.request, '测试记录已删除')
        return reverse('materials:batch_detail', kwargs={'pk': self.object.batch.pk})


class FatigueTestCreateView(CreateView):
    model = FatigueTest
    form_class = FatigueTestForm
    template_name = 'materials/fatigue_test_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.batch = get_object_or_404(MaterialBatch, pk=kwargs['batch_pk'])
        if not self.batch.can_add_fatigue_test():
            messages.error(request, '该批次处于断裂/审核/归档状态，无法新增疲劳测试记录')
            return redirect('materials:batch_detail', pk=self.batch.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['batch'] = self.batch
        existing = self.batch.fatigue_tests.filter(is_flagged=False)
        if existing.exists():
            cycles = list(existing.values_list('cycle_count', flat=True))
            loads = list(existing.values_list('load_force', flat=True))
            context['reference_stats'] = {
                'avg_cycles': round(sum(cycles) / len(cycles), 0),
                'min_cycles': min(cycles),
                'max_cycles': max(cycles),
                'avg_load': round(sum(loads) / len(loads), 2),
                'min_load': min(loads),
                'max_load': max(loads),
                'test_count': existing.count(),
            }
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['batch'] = self.batch
        return kwargs

    def form_valid(self, form):
        form.instance.batch = self.batch
        response = super().form_valid(form)
        self._check_and_create_anomaly(form.instance)
        return response

    def _check_and_create_anomaly(self, test):
        detector = AnomalyDetector(test.batch)
        anomalies = detector.check_fatigue_test(test, exclude_pk=test.pk)
        if anomalies:
            detector.create_anomaly_logs(
                anomalies, DataAnomalyLog.SOURCE_FATIGUE, test.pk
            )

    def get_success_url(self):
        messages.success(self.request, '疲劳测试记录添加成功')
        return reverse('materials:batch_detail', kwargs={'pk': self.batch.pk})


class FatigueTestUpdateView(UpdateView):
    model = FatigueTest
    form_class = FatigueTestForm
    template_name = 'materials/fatigue_test_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['batch'] = self.object.batch
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['batch'] = self.object.batch
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        detector = AnomalyDetector(self.object.batch)
        anomalies = detector.check_fatigue_test(self.object, exclude_pk=self.object.pk)
        if anomalies:
            detector.create_anomaly_logs(
                anomalies, DataAnomalyLog.SOURCE_FATIGUE, self.object.pk
            )
        return response

    def get_success_url(self):
        messages.success(self.request, '疲劳测试记录更新成功')
        return reverse('materials:batch_detail', kwargs={'pk': self.object.batch.pk})


class FatigueTestDeleteView(DeleteView):
    model = FatigueTest
    template_name = 'materials/fatigue_test_confirm_delete.html'

    def get_success_url(self):
        messages.success(self.request, '疲劳测试记录已删除')
        return reverse('materials:batch_detail', kwargs={'pk': self.object.batch.pk})


class ProcessParamCreateView(CreateView):
    model = MaterialProcessParam
    form_class = MaterialProcessParamForm
    template_name = 'materials/param_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.batch = get_object_or_404(MaterialBatch, pk=kwargs['batch_pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['batch'] = self.batch
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['batch'] = self.batch
        return kwargs

    def form_valid(self, form):
        form.instance.batch = self.batch
        return super().form_valid(form)

    def get_success_url(self):
        messages.success(self.request, '工艺参数添加成功')
        return reverse('materials:batch_detail', kwargs={'pk': self.batch.pk})


class ProcessParamUpdateView(UpdateView):
    model = MaterialProcessParam
    form_class = MaterialProcessParamForm
    template_name = 'materials/param_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['batch'] = self.object.batch
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['batch'] = self.object.batch
        return kwargs

    def get_success_url(self):
        messages.success(self.request, '工艺参数更新成功')
        return reverse('materials:batch_detail', kwargs={'pk': self.object.batch.pk})


class ProcessParamDeleteView(DeleteView):
    model = MaterialProcessParam
    template_name = 'materials/param_confirm_delete.html'

    def get_success_url(self):
        messages.success(self.request, '工艺参数已删除')
        return reverse('materials:batch_detail', kwargs={'pk': self.object.batch.pk})


class BatchCompareView(View):
    def get(self, request):
        batch_ids = request.GET.getlist('batches')
        batches = MaterialBatch.objects.filter(id__in=batch_ids) if batch_ids else []
        all_batches = MaterialBatch.objects.all()

        chart_datasets = []
        stress_strain_datasets = []
        colors = [
            '#2563eb', '#dc2626', '#16a34a', '#ca8a04',
            '#9333ea', '#0891b2', '#ea580c', '#4f46e5'
        ]
        for idx, batch in enumerate(batches):
            tests = batch.tension_tests.order_by('test_time')
            data = []
            ss_data = []
            for test in tests:
                data.append({
                    'x': float(test.elongation),
                    'y': float(test.tension_force),
                })
                if test.stress is not None and test.strain is not None:
                    ss_data.append({
                        'x': float(test.strain),
                        'y': float(test.stress),
                    })
            chart_datasets.append({
                'label': f'{batch.batch_number} - {batch.material_source}',
                'data': data,
                'color': colors[idx % len(colors)],
            })
            if ss_data:
                stress_strain_datasets.append({
                    'label': f'{batch.batch_number} - {batch.material_source}',
                    'data': ss_data,
                    'color': colors[idx % len(colors)],
                })

        comparison_table = []
        analyzer = StatisticsAnalyzer()
        for batch in batches:
            stats = analyzer.get_batch_comprehensive_stats(batch)
            comparison_table.append({
                'batch_number': batch.batch_number,
                'pk': batch.pk,
                'source': batch.material_source,
                'diameter': batch.diameter,
                'initial_length': batch.initial_length,
                'status': batch.get_status_display(),
                'is_broken': batch.is_broken,
                'tension_test_count': batch.test_count,
                'fatigue_test_count': batch.fatigue_test_count,
                'max_force': batch.max_tension_force,
                'max_elongation': batch.max_elongation,
                'avg_rebound': batch.avg_rebound_rate,
                'youngs_modulus': batch.youngs_modulus,
                'tensile_strength': batch.tensile_strength,
                'elongation_at_break': batch.elongation_at_break,
                'fatigue_cycles_to_failure': batch.fatigue_cycles_to_failure,
                'fatigue_endurance_limit': batch.fatigue_endurance_limit,
                'anomaly_count': batch.anomaly_count,
            })

        context = {
            'all_batches': all_batches,
            'selected_batches': batches,
            'selected_ids': [str(b.id) for b in batches],
            'chart_datasets_json': json.dumps(chart_datasets, ensure_ascii=False),
            'stress_strain_datasets_json': json.dumps(stress_strain_datasets, ensure_ascii=False),
            'comparison_table_json': json.dumps(comparison_table, ensure_ascii=False),
        }
        return render(request, 'materials/batch_compare.html', context)


class StatisticsView(View):
    def get(self, request):
        analyzer = StatisticsAnalyzer()
        global_stats = analyzer.get_global_statistics()

        batches = MaterialBatch.objects.all()
        tension_tests = TensionTest.objects.all()
        fatigue_tests = FatigueTest.objects.all()

        stats = {
            'total_batches': batches.count(),
            'total_tension_tests': tension_tests.count(),
            'total_fatigue_tests': fatigue_tests.count(),
            'broken_count': sum(1 for b in batches if b.is_broken),
            'abnormal_break_count': tension_tests.filter(abnormal_break=True).count(),
            'flagged_tension_count': tension_tests.filter(is_flagged=True).count(),
            'flagged_fatigue_count': fatigue_tests.filter(is_flagged=True).count(),
        }

        force_values = list(tension_tests.values_list('tension_force', flat=True))
        elongation_values = list(tension_tests.values_list('elongation', flat=True))
        rebound_values = list(
            tension_tests.filter(rebound_rate__isnull=False).values_list('rebound_rate', flat=True)
        )

        tension_stats = {}
        if force_values:
            tension_stats['force'] = analyzer.basic_stats(force_values)
        if elongation_values:
            tension_stats['elongation'] = analyzer.basic_stats(elongation_values)
        if rebound_values:
            tension_stats['rebound'] = analyzer.basic_stats(rebound_values)

        fatigue_stats = {}
        cycle_values = list(fatigue_tests.values_list('cycle_count', flat=True))
        load_values = list(fatigue_tests.values_list('load_force', flat=True))
        if cycle_values:
            fatigue_stats['cycles'] = analyzer.basic_stats(cycle_values)
        if load_values:
            fatigue_stats['load'] = analyzer.basic_stats(load_values)
        result_dist = {}
        for choice_val, choice_label in FatigueTest.RESULT_CHOICES:
            result_dist[choice_val] = {
                'label': choice_label,
                'count': fatigue_tests.filter(result=choice_val).count()
            }
        fatigue_stats['result_distribution'] = result_dist

        batch_comparison_data = []
        for batch in batches:
            batch_stats = analyzer.get_batch_comprehensive_stats(batch)
            row = {
                'label': batch.batch_number,
                'pk': batch.pk,
                'source': batch.material_source,
                'diameter': batch.diameter,
                'initial_length': batch.initial_length,
                'test_count': batch.test_count,
                'is_broken': batch.is_broken,
                'max_force': batch.max_tension_force or 0,
                'avg_force': (batch_stats.get('tension', {}) or {}).get('force', {}).get('mean', 0) if batch_stats.get('tension') else 0,
                'max_elongation': batch.max_elongation or 0,
                'avg_rebound': batch.avg_rebound_rate or 0,
                'youngs_modulus': batch.youngs_modulus,
                'tensile_strength': batch.tensile_strength,
                'elongation_at_break': batch.elongation_at_break,
            }
            batch_comparison_data.append(row)

        try:
            SnapshotGenerator.generate_daily()
        except Exception:
            pass

        snapshots = StatisticalSnapshot.objects.filter(
            snapshot_type=StatisticalSnapshot.SNAPSHOT_TYPE_DAILY
        ).order_by('-snapshot_date')[:30]
        snapshot_data = []
        for s in snapshots:
            snapshot_data.append({
                'date': s.snapshot_date.isoformat(),
                'total_batches': s.total_batches,
                'active_batches': s.active_batches,
                'broken_batches': s.broken_batches,
                'tension_tests': s.total_tension_tests,
                'fatigue_tests': s.total_fatigue_tests,
                'avg_force': s.avg_force or 0,
                'avg_rebound': s.avg_rebound_rate or 0,
                'anomalies': s.anomaly_count,
            })
        snapshot_data.reverse()

        context = {
            'stats': stats,
            'tension_stats': tension_stats,
            'fatigue_stats': fatigue_stats,
            'batch_comparison_data_json': json.dumps(batch_comparison_data, ensure_ascii=False),
            'global_stats': global_stats,
            'trend_data_json': json.dumps(global_stats.get('trend', []), ensure_ascii=False),
            'snapshot_data_json': json.dumps(snapshot_data, ensure_ascii=False),
            'source_distribution_json': json.dumps(
                global_stats.get('source_distribution', []), ensure_ascii=False
            ),
        }
        return render(request, 'materials/statistics.html', context)


class AnomalyListView(ListView):
    model = DataAnomalyLog
    template_name = 'materials/anomaly_list.html'
    context_object_name = 'anomalies'
    paginate_by = 20

    def get_queryset(self):
        queryset = DataAnomalyLog.objects.all()
        resolved = self.request.GET.get('resolved')
        if resolved == '0':
            queryset = queryset.filter(is_resolved=False)
        elif resolved == '1':
            queryset = queryset.filter(is_resolved=True)
        severity = self.request.GET.get('severity')
        if severity:
            queryset = queryset.filter(severity=severity)
        source = self.request.GET.get('source')
        if source:
            queryset = queryset.filter(source_type=source)
        return queryset.select_related('batch')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['resolved_filter'] = self.request.GET.get('resolved', '')
        context['severity_filter'] = self.request.GET.get('severity', '')
        context['source_filter'] = self.request.GET.get('source', '')
        context['severity_choices'] = DataAnomalyLog.SEVERITY_CHOICES
        context['source_choices'] = DataAnomalyLog.SOURCE_CHOICES
        total = DataAnomalyLog.objects.count()
        resolved = DataAnomalyLog.objects.filter(is_resolved=True).count()
        context['anomaly_summary'] = {
            'total': total,
            'resolved': resolved,
            'unresolved': total - resolved,
            'high': DataAnomalyLog.objects.filter(
                severity=DataAnomalyLog.SEVERITY_HIGH, is_resolved=False
            ).count(),
            'medium': DataAnomalyLog.objects.filter(
                severity=DataAnomalyLog.SEVERITY_MEDIUM, is_resolved=False
            ).count(),
            'low': DataAnomalyLog.objects.filter(
                severity=DataAnomalyLog.SEVERITY_LOW, is_resolved=False
            ).count(),
        }
        return context


class AnomalyResolveView(View):
    def get(self, request, pk):
        anomaly = get_object_or_404(DataAnomalyLog, pk=pk)
        if anomaly.is_resolved:
            messages.info(request, '该异常已处理')
            return redirect('materials:anomaly_list')
        form = AnomalyResolveForm(instance=anomaly)
        context = {
            'anomaly': anomaly,
            'form': form,
        }
        return render(request, 'materials/anomaly_resolve.html', context)

    def post(self, request, pk):
        anomaly = get_object_or_404(DataAnomalyLog, pk=pk)
        form = AnomalyResolveForm(request.POST, instance=anomaly)
        if form.is_valid():
            anomaly = form.save(commit=False)
            anomaly.is_resolved = True
            anomaly.resolved_at = timezone.now()
            anomaly.save()
            messages.success(request, '异常数据已处理')
            return redirect('materials:anomaly_list')
        context = {
            'anomaly': anomaly,
            'form': form,
        }
        return render(request, 'materials/anomaly_resolve.html', context)


class BatchStatsAPIView(View):
    def get(self, request, pk):
        batch = get_object_or_404(MaterialBatch, pk=pk)
        analyzer = StatisticsAnalyzer()
        stats = analyzer.get_batch_comprehensive_stats(batch)
        return JsonResponse(stats, safe=False, json_dumps_params={'ensure_ascii': False})


class GlobalStatsAPIView(View):
    def get(self, request):
        analyzer = StatisticsAnalyzer()
        stats = analyzer.get_global_statistics()
        return JsonResponse(stats, safe=False, json_dumps_params={'ensure_ascii': False})


class CalculateReboundAPIView(View):
    def get(self, request):
        try:
            initial_length = float(request.GET.get('initial_length', 0))
            length_before = float(request.GET.get('length_before', 0))
            length_after = float(request.GET.get('length_after', 0))
        except (TypeError, ValueError):
            return HttpResponseBadRequest('参数必须为数字')

        errors = ReboundRateCalculator.validate_inputs(
            initial_length, length_before, length_after
        )
        if errors:
            return JsonResponse({'success': False, 'errors': errors})

        result = ReboundRateCalculator.calculate(
            initial_length, length_before, length_after
        )
        return JsonResponse({
            'success': True,
            'rebound_rate': result,
        })
