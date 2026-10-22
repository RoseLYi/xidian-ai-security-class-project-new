import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { scientistApi, type ObsidianVault } from '@/lib/api'
import { Button } from '@/components/ui/button'

export function KnowledgeBaseWorkspace() {
  const [kind, setKind] = useState<ObsidianVault['kind']>('academic')
  const [path, setPath] = useState('')
  const queryClient = useQueryClient()
  const vaults = useQuery({
    queryKey: ['knowledgeVaults'],
    queryFn: async () => (await scientistApi.vaultsStatus()).data.vaults,
  })
  const notes = useQuery({
    queryKey: ['knowledgeNotes', kind],
    queryFn: async () => (await scientistApi.vaultNotesByKind(kind)).data.notes,
  })
  const note = useQuery({
    queryKey: ['knowledgeNote', kind, path],
    queryFn: async () => (await scientistApi.vaultNoteByKind(kind, path)).data,
    enabled: Boolean(path),
  })
  const sync = useMutation({
    mutationFn: () => scientistApi.syncVaults(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['knowledgeNotes'] })
      queryClient.invalidateQueries({ queryKey: ['knowledgeVaults'] })
    },
  })

  return (
    <section className="mx-auto max-w-5xl space-y-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">知识库</h1>
          <p className="mt-1 text-xs text-zinc-400">
            归档基于已分析的记录。请核对笔记中的原始来源。
          </p>
        </div>
        <Button onClick={() => sync.mutate()} disabled={sync.isPending}>
          {sync.isPending ? '正在同步…' : '同步分析记录'}
        </Button>
      </div>
      {sync.isError && (
        <p role="alert" className="text-sm text-rose-300">
          同步失败，请检查知识库路径和写入权限。
        </p>
      )}
      {sync.isSuccess && (
        <p role="status" className="text-sm text-emerald-300">
          同步完成，列表已刷新。
        </p>
      )}
      <div className="flex gap-3">
        {(['academic', 'social'] as const).map((value) => {
          const vault = vaults.data?.find((item) => item.kind === value)
          return (
            <button
              type="button"
              key={value}
              onClick={() => {
                setKind(value)
                setPath('')
              }}
              className={`rounded-lg border px-4 py-3 text-left ${kind === value ? 'border-cyan-400/60 bg-cyan-400/10' : 'border-white/10 bg-[#202020]'}`}
            >
              <span className="text-sm">
                {value === 'academic' ? '学术知识库' : '社交知识库'}
              </span>
              <span className="mt-1 block text-xs text-zinc-400">
                {vault?.available
                  ? `${vault.note_count} 篇笔记`
                  : '尚未配置或目录不可用'}
              </span>
            </button>
          )
        })}
      </div>
      {notes.isError && (
        <p role="alert" className="text-sm text-rose-300">
          笔记列表读取失败。
        </p>
      )}
      <div className="grid gap-4 md:grid-cols-[260px_minmax(0,1fr)]">
        <div className="max-h-[60vh] space-y-2 overflow-auto">
          {(notes.data || []).map((item) => (
            <button
              type="button"
              key={item.path}
              onClick={() => setPath(item.path)}
              className={`block w-full rounded-md border p-3 text-left text-sm ${path === item.path ? 'border-cyan-400/60 text-cyan-200' : 'border-white/10 text-zinc-300'}`}
            >
              {item.title || item.path}
            </button>
          ))}
          {!notes.isLoading && !notes.data?.length && (
            <p className="text-sm text-zinc-400">
              暂无归档，先完成资料分析再同步。
            </p>
          )}
        </div>
        <div className="min-w-0 rounded-lg border border-white/10 bg-[#202020] p-4">
          {path ? (
            note.isError ? (
              <p role="alert" className="text-sm text-rose-300">
                笔记读取失败。
              </p>
            ) : (
              <pre className="max-h-[60vh] overflow-auto whitespace-pre-wrap break-words text-sm leading-7 text-zinc-300">
                {note.data?.content || '正在读取…'}
              </pre>
            )
          ) : (
            <p className="text-sm text-zinc-400">选择一篇笔记查看归档内容。</p>
          )}
        </div>
      </div>
    </section>
  )
}
