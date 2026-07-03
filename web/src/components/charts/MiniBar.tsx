import { AreaChart, Area, ResponsiveContainer } from 'recharts';

interface MiniBarProps {
  data?: { value: number }[];
  color?: string;
}

const defaultData = [
  { value: 82 }, { value: 124 }, { value: 98 }, { value: 156 },
  { value: 113 }, { value: 169 }, { value: 132 },
];

export default function MiniBar({ data = defaultData, color = '#8b5cf6' }: MiniBarProps) {
  return (
    <ResponsiveContainer width="100%" height={42}>
      <AreaChart data={data}>
        <Area
          type="monotone"
          dataKey="value"
          stroke={color}
          fill={color}
          fillOpacity={0.18}
          strokeWidth={2}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
