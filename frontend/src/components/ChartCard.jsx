import { Card, CardHeader, CardTitle, CardSub, CardContent } from '@/components/ui/card';

export default function ChartCard({ title, sub, height = 'h-[280px]', children }) {
  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>{title}</CardTitle>
          {sub && <CardSub>{sub}</CardSub>}
        </div>
      </CardHeader>
      <CardContent>
        <div className={`relative ${height}`}>{children}</div>
      </CardContent>
    </Card>
  );
}
