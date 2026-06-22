from materials.models import DataAnomalyLog


def unresolved_anomaly_count(request):
    return {
        'unresolved_anomaly_count': DataAnomalyLog.objects.filter(is_resolved=False).count(),
    }
