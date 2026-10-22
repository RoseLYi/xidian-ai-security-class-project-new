import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { dataApi } from '@/lib/api'
import { Button } from '@/components/ui/button'

export function DataExplorer() {
  const [selected, setSelected] = useState('')
  const [filter, setFilter] = useState('')
  const files = useQuery({
    queryKey: ['dataExplorerFiles'],
    queryFn: async () => (await dataApi.getFiles()).data.files,
  })
  const preview = useQuery({
    queryKey: ['dataExplorerPreview', selected],
    queryFn: async () => (await dataApi.getFileContent(selected, 30)).data,
    enabled: Boolean(selected),
  })
  const visible = (files.data || []).filter((file) =>
    file.path.toLowerCase().includes(filter.toLowerCase())
  )

  return (
    <section className="flex h-full min-h-[360px] flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">采集结果</h1>
          <p className="mt-1 text-xs text-zinc-400">
            预览前 30 条记录，完整内容可下载查看。
          </p>
        </div>
        <Button variant="outline" onClick={() => files.refetch()}>
          刷新文件
        </Button>
      </div>
      <input
        aria-label="搜索文件"
        value={filter}
        onChange={(event) => setFilter(event.target.value)}
        placeholder="按文件路径搜索"
        className="rounded-md border border-white/10 bg-[#202020] px-3 py-2 text-sm"
      />
      {files.isError && (
        <p role="alert" className="text-sm text-rose-300">
          文件列表加载失败，请刷新重试。
        </p>
      )}
      <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 md:grid-cols-[280px_minmax(0,1fr)]">
        <div className="max-h-[65vh] space-y-2 overflow-auto">
          {visible.map((file) => (
            <button
              type="button"
              key={file.path}
              onClick={() => setSelected(file.path)}
              className={`block w-full rounded-lg border p-3 text-left ${selected === file.path ? 'border-cyan-400/60 bg-cyan-400/10' : 'border-white/10 bg-[#202020]'}`}
            >
              <span className="block break-all text-sm">{file.path}</span>
              <span className="mt-1 block text-xs text-zinc-400">
                {file.record_count ?? '—'} 条 · {file.type}
              </span>
            </button>
          ))}
          {!files.isLoading && visible.length === 0 && (
            <p className="text-sm text-zinc-400">暂无匹配文件。</p>
          )}
        </div>
        <div className="min-w-0 rounded-lg border border-white/10 bg-[#202020] p-4">
          {selected ? (
            <>
              <div className="mb-3 flex items-start justify-between gap-3">
                <h2 className="break-all text-sm">{selected}</h2>
                <a
                  href={dataApi.getDownloadUrl(selected)}
                  className="shrink-0 text-sm text-cyan-300"
                >
                  下载
                </a>
              </div>
              {preview.isLoading ? (
                <p className="text-sm text-zinc-400">正在读取…</p>
              ) : preview.isError ? (
                <p role="alert" className="text-sm text-rose-300">
                  无法预览此文件，可下载后查看。
                </p>
              ) : (
                <pre className="max-h-[55vh] overflow-auto whitespace-pre-wrap break-words text-xs leading-6 text-zinc-300">
                  {JSON.stringify(preview.data?.data || [], null, 2)}
                </pre>
              )}
            </>
          ) : (
            <p className="text-sm text-zinc-400">
              选择一个文件查看原始记录与来源。
            </p>
          )}
        </div>
      </div>
    </section>
  )
}
