import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';

// Opportunity pipeline-by-stage strip.
export default function Stages({ title = 'Pipeline by Stage', stages = [], total = 0 }) {
  return (
    <Card>
      <CardHeader><CardTitle>{title}</CardTitle></CardHeader>
      <CardContent>
        {stages.length ? (
          <div className="stages">
            {stages.map((s) => (
              <div key={s.label} className="stage">
                <div className="stage-name">{s.label}</div>
                <div className="stage-cnt">{s.count}</div>
                <div className="stage-pct">{total ? ((s.count / total) * 100).toFixed(0) : 0}% of pipeline</div>
              </div>
            ))}
          </div>
        ) : <div className="crm-empty">No stages</div>}
      </CardContent>
    </Card>
  );
}
