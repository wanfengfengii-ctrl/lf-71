import json

from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView
)
from django.contrib import messages

from .models import MaterialBatch, TensionTest
from .forms import MaterialBatchForm, TensionTestForm


class DashboardView(View):
    def get(self, request):
        batches = MaterialBatch.objects.all()
        total_batches = batches.count()
        broken_batches = sum(1 for b in batches if b.is_broken)
        active_batches = total_batches - broken_batches
        total_tests = TensionTest.objects.count()
        recent_batches = batches[:5]
        recent_tests = TensionTest.objects.all()[:10]
        context = {
            'total_batches': total_batches,
            'broken_batches': broken_batches,
            'active_batches': active_batches,
            'total_tests': total_tests,
            'recent_batches': recent_batches,
            'recent_tests': recent_tests,
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
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        return context


class MaterialBatchDetailView(DetailView):
    model = MaterialBatch
    template_name = 'materials/batch_detail.html'
    context_object_name = 'batch'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tests = self.object.tension_tests.order_by('test_time')
        context['tests'] = tests
        chart_data = []
        for test in tests:
            chart_data.append({
                'x': float(test.elongation),
                'y': float(test.tension_force),
                'broken': test.is_broken,
                'time': test.test_time.strftime('%Y-%m-%d %H:%M'),
            })
        context['chart_data_json'] = json.dumps(chart_data, ensure_ascii=False)
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


class TensionTestCreateView(CreateView):
    model = TensionTest
    form_class = TensionTestForm
    template_name = 'materials/test_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.batch = get_object_or_404(MaterialBatch, pk=kwargs['batch_pk'])
        if self.batch.is_broken:
            messages.error(request, '该批次样本已断裂，无法新增测试记录')
            return redirect('materials:batch_detail', pk=self.batch.pk)
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

    def get_success_url(self):
        messages.success(self.request, '测试记录更新成功')
        return reverse('materials:batch_detail', kwargs={'pk': self.object.batch.pk})


class TensionTestDeleteView(DeleteView):
    model = TensionTest
    template_name = 'materials/test_confirm_delete.html'

    def get_success_url(self):
        messages.success(self.request, '测试记录已删除')
        return reverse('materials:batch_detail', kwargs={'pk': self.object.batch.pk})


class BatchCompareView(View):
    def get(self, request):
        batch_ids = request.GET.getlist('batches')
        batches = MaterialBatch.objects.filter(id__in=batch_ids) if batch_ids else []
        all_batches = MaterialBatch.objects.all()

        chart_datasets = []
        colors = [
            '#2563eb', '#dc2626', '#16a34a', '#ca8a04',
            '#9333ea', '#0891b2', '#ea580c', '#4f46e5'
        ]
        for idx, batch in enumerate(batches):
            tests = batch.tension_tests.order_by('test_time')
            data = []
            for test in tests:
                data.append({
                    'x': float(test.elongation),
                    'y': float(test.tension_force),
                })
            chart_datasets.append({
                'label': f'{batch.batch_number} - {batch.material_source}',
                'data': data,
                'color': colors[idx % len(colors)],
            })

        context = {
            'all_batches': all_batches,
            'selected_batches': batches,
            'selected_ids': [str(b.id) for b in batches],
            'chart_datasets_json': json.dumps(chart_datasets, ensure_ascii=False),
        }
        return render(request, 'materials/batch_compare.html', context)
