import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function KeysPage() {
  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-3xl font-bold">API Keys</h1>
        <p className="text-[rgb(var(--text-muted))]">Manage your API keys and tokens</p>
      </div>
      
      <Card>
        <CardHeader>
          <CardTitle>Your API Keys</CardTitle>
          <CardDescription>
            No API keys yet. Create your first key to get started.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-[rgb(var(--text-muted))]">
            API key management will be implemented in the next phase.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
