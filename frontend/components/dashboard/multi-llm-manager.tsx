'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import {
  Brain,
  Zap,
  Settings,
  TestTube,
  BarChart3,
  CheckCircle,
  AlertTriangle,
  Cpu,
  Globe,
  Shield,
  Clock,
  DollarSign
} from 'lucide-react';
import { Progress } from '@/components/ui/progress';

interface LLMProvider {
  id: string;
  name: string;
  icon: string;
  models: Array<{
    id: string;
    name: string;
    context_length: number;
    cost_per_token: number;
    speed_rating: number;
    accuracy_rating: number;
  }>;
  status: 'active' | 'inactive' | 'error';
  usage: {
    requests_today: number;
    tokens_used: number;
    cost_today: number;
  };
}

export function MultiLLMManager() {
  const [providers, setProviders] = useState<LLMProvider[]>([]);
  const [selectedProvider, setSelectedProvider] = useState<string>('');
  const [testPrompt, setTestPrompt] = useState('');
  const [testResults, setTestResults] = useState<any[]>([]);
  const [isComparing, setIsComparing] = useState(false);
  const [autoFailover, setAutoFailover] = useState(true);

  useEffect(() => {
    // Load LLM providers data
    setProviders([
      {
        id: 'anthropic',
        name: 'Anthropic Claude',
        icon: '🤖',
        models: [
          {
            id: 'claude-3-opus',
            name: 'Claude 3 Opus',
            context_length: 200000,
            cost_per_token: 0.000015,
            speed_rating: 85,
            accuracy_rating: 98
          },
          {
            id: 'claude-3-sonnet',
            name: 'Claude 3 Sonnet',
            context_length: 200000,
            cost_per_token: 0.000003,
            speed_rating: 95,
            accuracy_rating: 94
          }
        ],
        status: 'active',
        usage: {
          requests_today: 1247,
          tokens_used: 2456789,
          cost_today: 36.85
        }
      },
      {
        id: 'openai',
        name: 'OpenAI GPT',
        icon: '🧠',
        models: [
          {
            id: 'gpt-4-turbo',
            name: 'GPT-4 Turbo',
            context_length: 128000,
            cost_per_token: 0.00001,
            speed_rating: 90,
            accuracy_rating: 95
          },
          {
            id: 'gpt-3.5-turbo',
            name: 'GPT-3.5 Turbo',
            context_length: 16385,
            cost_per_token: 0.0000005,
            speed_rating: 98,
            accuracy_rating: 87
          }
        ],
        status: 'active',
        usage: {
          requests_today: 892,
          tokens_used: 1234567,
          cost_today: 12.35
        }
      },
      {
        id: 'cohere',
        name: 'Cohere Command',
        icon: '⚡',
        models: [
          {
            id: 'command-r-plus',
            name: 'Command R+',
            context_length: 128000,
            cost_per_token: 0.000003,
            speed_rating: 92,
            accuracy_rating: 91
          }
        ],
        status: 'inactive',
        usage: {
          requests_today: 0,
          tokens_used: 0,
          cost_today: 0
        }
      },
      {
        id: 'local',
        name: 'Local Models (Ollama)',
        icon: '🏠',
        models: [
          {
            id: 'llama2-70b',
            name: 'Llama 2 70B',
            context_length: 4096,
            cost_per_token: 0,
            speed_rating: 75,
            accuracy_rating: 88
          }
        ],
        status: 'inactive',
        usage: {
          requests_today: 0,
          tokens_used: 0,
          cost_today: 0
        }
      }
    ]);
  }, []);

  const handleProviderTest = async (providerId: string) => {
    setIsComparing(true);
    // Simulate API test
    setTimeout(() => {
      setTestResults(prev => [
        ...prev,
        {
          provider: providerId,
          response_time: Math.random() * 3 + 1,
          accuracy_score: Math.random() * 20 + 80,
          cost: Math.random() * 0.01,
          timestamp: new Date().toISOString()
        }
      ]);
      setIsComparing(false);
    }, 2000);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
        return 'bg-emerald-500';
      case 'inactive':
        return 'bg-gray-400';
      case 'error':
        return 'bg-red-500';
      default:
        return 'bg-gray-400';
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
            Multi-LLM Engine
          </h1>
          <p className="text-muted-foreground mt-1">
            Intelligent model routing and performance optimization
          </p>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Label htmlFor="auto-failover">Auto-Failover</Label>
            <Switch
              id="auto-failover"
              checked={autoFailover}
              onCheckedChange={setAutoFailover}
            />
          </div>
          <Button variant="outline">
            <Settings className="h-4 w-4 mr-2" />
            Configure
          </Button>
        </div>
      </div>

      <Tabs defaultValue="overview" className="space-y-6">
        <TabsList className="grid grid-cols-4 w-full max-w-md">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="models">Models</TabsTrigger>
          <TabsTrigger value="testing">Testing</TabsTrigger>
          <TabsTrigger value="analytics">Analytics</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-6">
          {/* Provider Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {providers.map((provider) => (
              <Card key={provider.id} className="relative overflow-hidden">
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-2xl">{provider.icon}</span>
                      <CardTitle className="text-lg">{provider.name}</CardTitle>
                    </div>
                    <div className={`w-3 h-3 rounded-full ${getStatusColor(provider.status)}`} />
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div>
                      <span className="text-muted-foreground">Requests</span>
                      <div className="font-semibold">{provider.usage.requests_today.toLocaleString()}</div>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Cost</span>
                      <div className="font-semibold">${provider.usage.cost_today.toFixed(2)}</div>
                    </div>
                  </div>
                  <div>
                    <div className="flex justify-between text-sm mb-1">
                      <span>Token Usage</span>
                      <span>{(provider.usage.tokens_used / 1000000).toFixed(1)}M</span>
                    </div>
                    <Progress value={Math.min((provider.usage.tokens_used / 10000000) * 100, 100)} />
                  </div>
                  <Button
                    variant={provider.status === 'active' ? 'secondary' : 'default'}
                    size="sm"
                    className="w-full"
                    onClick={() => handleProviderTest(provider.id)}
                  >
                    {provider.status === 'active' ? 'Test Performance' : 'Activate'}
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="models" className="space-y-6">
          <div className="grid gap-6">
            {providers.map((provider) => (
              <Card key={provider.id}>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <span className="text-xl">{provider.icon}</span>
                    {provider.name} Models
                  </CardTitle>
                  <CardDescription>
                    Available models and their specifications
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {provider.models.map((model) => (
                      <div key={model.id} className="p-4 rounded-lg bg-muted/30 space-y-3">
                        <div className="flex items-center justify-between">
                          <h4 className="font-semibold">{model.name}</h4>
                          <Badge variant="outline">{model.id}</Badge>
                        </div>
                        
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                          <div className="flex items-center gap-2">
                            <Globe className="h-4 w-4 text-muted-foreground" />
                            <div>
                              <div className="text-muted-foreground">Context Length</div>
                              <div className="font-medium">{model.context_length.toLocaleString()}</div>
                            </div>
                          </div>
                          
                          <div className="flex items-center gap-2">
                            <DollarSign className="h-4 w-4 text-muted-foreground" />
                            <div>
                              <div className="text-muted-foreground">Cost/Token</div>
                              <div className="font-medium">${model.cost_per_token.toFixed(6)}</div>
                            </div>
                          </div>
                          
                          <div className="flex items-center gap-2">
                            <Zap className="h-4 w-4 text-muted-foreground" />
                            <div>
                              <div className="text-muted-foreground">Speed</div>
                              <div className="flex items-center gap-1">
                                <Progress value={model.speed_rating} className="w-16 h-2" />
                                <span className="font-medium text-xs">{model.speed_rating}%</span>
                              </div>
                            </div>
                          </div>
                          
                          <div className="flex items-center gap-2">
                            <Brain className="h-4 w-4 text-muted-foreground" />
                            <div>
                              <div className="text-muted-foreground">Accuracy</div>
                              <div className="flex items-center gap-1">
                                <Progress value={model.accuracy_rating} className="w-16 h-2" />
                                <span className="font-medium text-xs">{model.accuracy_rating}%</span>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="testing" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <TestTube className="h-5 w-5 text-primary" />
                Model Performance Testing
              </CardTitle>
              <CardDescription>
                Compare model performance across different providers
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="space-y-4">
                  <div>
                    <Label htmlFor="test-prompt">Test Prompt</Label>
                    <Textarea
                      id="test-prompt"
                      placeholder="Enter a test prompt to evaluate model performance..."
                      value={testPrompt}
                      onChange={(e) => setTestPrompt(e.target.value)}
                      className="mt-2"
                    />
                  </div>
                  
                  <div>
                    <Label htmlFor="provider-select">Select Provider</Label>
                    <Select value={selectedProvider} onValueChange={setSelectedProvider}>
                      <SelectTrigger className="mt-2">
                        <SelectValue placeholder="Choose a provider to test" />
                      </SelectTrigger>
                      <SelectContent>
                        {providers.map((provider) => (
                          <SelectItem key={provider.id} value={provider.id}>
                            {provider.icon} {provider.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  
                  <Button
                    className="w-full"
                    onClick={() => selectedProvider && handleProviderTest(selectedProvider)}
                    disabled={!selectedProvider || !testPrompt || isComparing}
                  >
                    {isComparing ? (
                      <>
                        <Clock className="h-4 w-4 mr-2 animate-spin" />
                        Testing...
                      </>
                    ) : (
                      <>
                        <TestTube className="h-4 w-4 mr-2" />
                        Run Test
                      </>
                    )}
                  </Button>
                </div>
                
                <div className="space-y-4">
                  <h4 className="font-semibold">Test Results</h4>
                  {testResults.length > 0 ? (
                    <div className="space-y-2 max-h-80 overflow-y-auto">
                      {testResults.map((result, index) => (
                        <div key={index} className="p-3 rounded-lg bg-muted/30">
                          <div className="flex items-center justify-between mb-2">
                            <Badge variant="outline">
                              {providers.find(p => p.id === result.provider)?.name}
                            </Badge>
                            <span className="text-xs text-muted-foreground">
                              {new Date(result.timestamp).toLocaleTimeString()}
                            </span>
                          </div>
                          <div className="grid grid-cols-3 gap-2 text-sm">
                            <div>
                              <div className="text-muted-foreground">Response</div>
                              <div className="font-medium">{result.response_time.toFixed(2)}s</div>
                            </div>
                            <div>
                              <div className="text-muted-foreground">Accuracy</div>
                              <div className="font-medium">{result.accuracy_score.toFixed(1)}%</div>
                            </div>
                            <div>
                              <div className="text-muted-foreground">Cost</div>
                              <div className="font-medium">${result.cost.toFixed(4)}</div>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-center text-muted-foreground py-8">
                      No test results yet. Run a test to see performance metrics.
                    </div>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="analytics" className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Today's Usage</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-primary">
                  {providers.reduce((acc, p) => acc + p.usage.requests_today, 0).toLocaleString()}
                </div>
                <p className="text-xs text-muted-foreground mt-1">Total requests across all providers</p>
              </CardContent>
            </Card>
            
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Total Cost Today</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-primary">
                  ${providers.reduce((acc, p) => acc + p.usage.cost_today, 0).toFixed(2)}
                </div>
                <p className="text-xs text-muted-foreground mt-1">Across all active providers</p>
              </CardContent>
            </Card>
            
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Active Providers</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-primary">
                  {providers.filter(p => p.status === 'active').length}/{providers.length}
                </div>
                <p className="text-xs text-muted-foreground mt-1">Healthy and operational</p>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}