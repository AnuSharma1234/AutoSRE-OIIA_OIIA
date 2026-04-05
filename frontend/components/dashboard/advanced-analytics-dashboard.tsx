'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  AreaChart,
  Area
} from 'recharts';
import {
  Activity,
  TrendingUp,
  Clock,
  Zap,
  Shield,
  Brain,
  Target,
  AlertTriangle,
  CheckCircle,
  RefreshCw,
  Download
} from 'lucide-react';
import { MetricCard } from '@/components/ui/metric-card';

interface AnalyticsData {
  incidentTrends: Array<{
    date: string;
    incidents: number;
    resolved: number;
    autoResolved: number;
  }>;
  resolutionTimes: Array<{
    type: string;
    avgTime: number;
    count: number;
  }>;
  aiPerformance: Array<{
    date: string;
    accuracy: number;
    responseTime: number;
    successRate: number;
  }>;
  serviceCoverage: Array<{
    service: string;
    incidents: number;
    coverage: number;
    color: string;
  }>;
  keyMetrics: {
    totalIncidents: number;
    autoResolvedPercentage: number;
    avgResolutionTime: number;
    aiAccuracy: number;
    uptime: number;
    costSavings: number;
  };
}

export function AdvancedAnalyticsDashboard() {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [timeRange, setTimeRange] = useState('7d');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Simulate loading advanced analytics data
    setTimeout(() => {
      setData({
        incidentTrends: [
          { date: '2024-01', incidents: 45, resolved: 42, autoResolved: 35 },
          { date: '2024-02', incidents: 38, resolved: 36, autoResolved: 31 },
          { date: '2024-03', incidents: 52, resolved: 49, autoResolved: 43 },
          { date: '2024-04', incidents: 31, resolved: 30, autoResolved: 28 },
          { date: '2024-05', incidents: 29, resolved: 28, autoResolved: 26 },
        ],
        resolutionTimes: [
          { type: 'Critical', avgTime: 4.2, count: 23 },
          { type: 'High', avgTime: 8.7, count: 45 },
          { type: 'Medium', avgTime: 15.3, count: 67 },
          { type: 'Low', avgTime: 32.1, count: 89 },
        ],
        aiPerformance: [
          { date: '2024-01', accuracy: 85, responseTime: 2.3, successRate: 82 },
          { date: '2024-02', accuracy: 88, responseTime: 2.1, successRate: 86 },
          { date: '2024-03', accuracy: 92, responseTime: 1.9, successRate: 90 },
          { date: '2024-04', accuracy: 94, responseTime: 1.7, successRate: 93 },
          { date: '2024-05', accuracy: 96, responseTime: 1.5, successRate: 95 },
        ],
        serviceCoverage: [
          { service: 'API Gateway', incidents: 35, coverage: 98, color: '#3B82F6' },
          { service: 'Database', incidents: 22, coverage: 95, color: '#10B981' },
          { service: 'Frontend', incidents: 18, coverage: 92, color: '#8B5CF6' },
          { service: 'Cache Layer', incidents: 12, coverage: 88, color: '#F59E0B' },
          { service: 'Message Queue', incidents: 8, coverage: 85, color: '#EF4444' },
        ],
        keyMetrics: {
          totalIncidents: 195,
          autoResolvedPercentage: 87.2,
          avgResolutionTime: 12.4,
          aiAccuracy: 95.8,
          uptime: 99.97,
          costSavings: 45600
        }
      });
      setLoading(false);
    }, 1000);
  }, [timeRange]);

  if (loading || !data) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="flex items-center gap-2">
          <RefreshCw className="h-5 w-5 animate-spin text-primary" />
          <span>Loading advanced analytics...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
            Advanced Analytics
          </h1>
          <p className="text-muted-foreground mt-1">
            AI-powered insights and performance metrics
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Tabs value={timeRange} onValueChange={setTimeRange}>
            <TabsList>
              <TabsTrigger value="7d">7 Days</TabsTrigger>
              <TabsTrigger value="30d">30 Days</TabsTrigger>
              <TabsTrigger value="90d">90 Days</TabsTrigger>
            </TabsList>
          </Tabs>
          <Button variant="outline" size="sm">
            <Download className="h-4 w-4 mr-2" />
            Export
          </Button>
        </div>
      </div>

      {/* Key Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        <MetricCard
          title="Total Incidents"
          value={data.keyMetrics.totalIncidents}
          icon={Activity}
          variant="info"
          change={{
            value: -12.5,
            type: 'decrease',
            timeframe: 'vs last month'
          }}
        />
        <MetricCard
          title="Auto-Resolved"
          value={data.keyMetrics.autoResolvedPercentage}
          format="percentage"
          icon={CheckCircle}
          variant="success"
          change={{
            value: 8.3,
            type: 'increase',
            timeframe: 'vs last month'
          }}
        />
        <MetricCard
          title="Avg Resolution Time"
          value={`${data.keyMetrics.avgResolutionTime}min`}
          icon={Clock}
          variant="warning"
          change={{
            value: -23.1,
            type: 'decrease',
            timeframe: 'vs last month'
          }}
        />
        <MetricCard
          title="AI Accuracy"
          value={data.keyMetrics.aiAccuracy}
          format="percentage"
          icon={Brain}
          variant="success"
          change={{
            value: 2.8,
            type: 'increase',
            timeframe: 'vs last month'
          }}
        />
        <MetricCard
          title="System Uptime"
          value={data.keyMetrics.uptime}
          format="percentage"
          icon={Shield}
          variant="success"
          change={{
            value: 0.1,
            type: 'increase',
            timeframe: 'vs last month'
          }}
        />
        <MetricCard
          title="Cost Savings"
          value={data.keyMetrics.costSavings}
          format="currency"
          icon={Target}
          variant="success"
          change={{
            value: 34.7,
            type: 'increase',
            timeframe: 'vs last month'
          }}
        />
      </div>

      {/* Analytics Tabs */}
      <Tabs defaultValue="trends" className="space-y-6">
        <TabsList className="grid grid-cols-4 w-full max-w-md">
          <TabsTrigger value="trends">Trends</TabsTrigger>
          <TabsTrigger value="performance">AI Performance</TabsTrigger>
          <TabsTrigger value="services">Services</TabsTrigger>
          <TabsTrigger value="resolution">Resolution</TabsTrigger>
        </TabsList>

        <TabsContent value="trends" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <TrendingUp className="h-5 w-5 text-primary" />
                Incident Trends Analysis
              </CardTitle>
              <CardDescription>
                Track incident patterns and auto-resolution rates over time
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={400}>
                <AreaChart data={data.incidentTrends}>
                  <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
                  <XAxis dataKey="date" />
                  <YAxis />
                  <Tooltip />
                  <Area
                    type="monotone"
                    dataKey="incidents"
                    stackId="1"
                    stroke="hsl(var(--primary))"
                    fill="hsl(var(--primary) / 0.1)"
                    name="Total Incidents"
                  />
                  <Area
                    type="monotone"
                    dataKey="autoResolved"
                    stackId="2"
                    stroke="hsl(var(--accent))"
                    fill="hsl(var(--accent) / 0.1)"
                    name="Auto-Resolved"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="performance" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Brain className="h-5 w-5 text-primary" />
                AI Performance Metrics
              </CardTitle>
              <CardDescription>
                Monitor AI agent accuracy and response times
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={400}>
                <LineChart data={data.aiPerformance}>
                  <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
                  <XAxis dataKey="date" />
                  <YAxis />
                  <Tooltip />
                  <Line
                    type="monotone"
                    dataKey="accuracy"
                    stroke="hsl(var(--primary))"
                    strokeWidth={3}
                    name="Accuracy %"
                  />
                  <Line
                    type="monotone"
                    dataKey="successRate"
                    stroke="hsl(var(--accent))"
                    strokeWidth={3}
                    name="Success Rate %"
                  />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="services" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Service Coverage Distribution</CardTitle>
                <CardDescription>
                  Incident distribution across monitored services
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie
                      data={data.serviceCoverage}
                      cx="50%"
                      cy="50%"
                      outerRadius={80}
                      dataKey="incidents"
                      label={({service, incidents}) => `${service}: ${incidents}`}
                    >
                      {data.serviceCoverage.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Service Health Scores</CardTitle>
                <CardDescription>
                  Coverage and reliability metrics per service
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {data.serviceCoverage.map((service) => (
                  <div key={service.service} className="flex items-center justify-between p-3 rounded-lg bg-muted/30">
                    <div className="flex items-center gap-3">
                      <div
                        className="w-3 h-3 rounded-full"
                        style={{ backgroundColor: service.color }}
                      />
                      <span className="font-medium">{service.service}</span>
                    </div>
                    <div className="flex items-center gap-4">
                      <Badge variant="outline">{service.incidents} incidents</Badge>
                      <Badge 
                        variant={service.coverage > 95 ? "default" : service.coverage > 90 ? "secondary" : "destructive"}
                      >
                        {service.coverage}% coverage
                      </Badge>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="resolution" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Clock className="h-5 w-5 text-primary" />
                Resolution Time Analysis
              </CardTitle>
              <CardDescription>
                Average resolution times by incident severity
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={400}>
                <BarChart data={data.resolutionTimes} layout="horizontal">
                  <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
                  <XAxis type="number" />
                  <YAxis dataKey="type" type="category" />
                  <Tooltip />
                  <Bar
                    dataKey="avgTime"
                    fill="hsl(var(--primary))"
                    radius={[0, 4, 4, 0]}
                    name="Avg Resolution Time (min)"
                  />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}