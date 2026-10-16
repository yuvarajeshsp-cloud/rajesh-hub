import { Button, Card, CardContent, CardHeader, CardTitle, ModeToggle, Toaster } from "@rajesh-hub/ui"
import { printTestPage, PrinterError } from "@rajesh-hub/print"
import { toast } from "sonner"

// Starter screen wired to the hub: theme toggle, a card and the thermal printer.
// Replace it with the app's first real page.
export default function App() {
  async function testPrinter() {
    try {
      await printTestPage()
      toast.success("Test page sent to the printer")
    } catch (err) {
      toast.error(err instanceof PrinterError ? err.message : "Could not print")
    }
  }

  return (
    <main className="mx-auto flex min-h-svh max-w-lg flex-col gap-4 p-4">
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">New App</h1>
        <ModeToggle />
      </header>
      <Card>
        <CardHeader>
          <CardTitle>Built from Rajesh Hub</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3 text-sm text-muted-foreground">
          <p>Brand colours, components, printing, offline storage and native helpers come from the shared packages.</p>
          <Button onClick={testPrinter}>Print a test receipt</Button>
        </CardContent>
      </Card>
      <Toaster />
    </main>
  )
}
