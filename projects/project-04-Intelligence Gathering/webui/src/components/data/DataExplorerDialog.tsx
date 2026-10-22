import { Database } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { DataExplorer } from './DataExplorer'

export function DataExplorerDialog() {
  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="ghost" size="sm" title="查看采集结果">
          <Database className="h-4 w-4" />
          <span className="sr-only">查看采集结果</span>
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[90vh] max-w-5xl overflow-auto border-white/10 bg-[#171717] text-zinc-100">
        <DialogHeader>
          <DialogTitle>资料文件浏览</DialogTitle>
        </DialogHeader>
        <DataExplorer />
      </DialogContent>
    </Dialog>
  )
}
