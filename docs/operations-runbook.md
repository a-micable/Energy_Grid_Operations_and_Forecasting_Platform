# GridMind Operations Runbook

## Emergency Balancing Procedure

1. Check latest balancing snapshot: `GET /api/v1/balancing/zones/{zone_id}/latest`
2. If imbalance > 50 MW, trigger balancing: `POST /api/v1/balancing/execute`
3. Monitor balancing actions in audit trail
4. If reserve inadequate, initiate emergency battery discharge

## Forecast Drift Response

1. Review drift-flagged revisions in audit log
2. Validate against SCADA actuals
3. If legitimate, force revision with documented reason
4. Update model parameters if systematic drift detected

## Outage Conflict Resolution

1. Query overlapping outages for affected resources
2. Review dependency graph for sequencing constraints
3. Run schedule optimization with buffer adjustment
4. Obtain approval before transitioning to APPROVED status

## Event Dead Letter Recovery

1. Monitor dead letter queue depth
2. Investigate ordering violations first
3. Reprocess with corrected sequence numbers
4. Escalate persistent failures to engineering
