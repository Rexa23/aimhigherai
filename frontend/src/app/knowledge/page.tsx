'use client'
import { useState } from 'react'
import useSWR from 'swr'
import { fetcher, knowledgeApi } from '../../lib/api'
import { Upload, Search, CheckCircle, Clock, Loader2, X } from 'lucide-react'
import { motion } from 'framer-motion'
import { DashboardTopbar } from '../../components/DashboardTopbar'

interface KnowledgeDoc {
  id: string
  title: string
  source_url: string | null
  is_indexed: boolean
  created_at: string
  indexed_at: string | null
}

interface SearchResult {
  chunk: string
  source_title: string
  source_url: string | null
  score: number
}

function DocumentCard({ doc }: { doc: KnowledgeDoc }) {
  return (
    <motion.div
      className="card-premium p-4"
      whileHover={{ y: -1 }}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold truncate" style={{ color: 'var(--text-primary)' }}>
            {doc.title}
          </h3>
          {doc.source_url && (
            <a
              href={doc.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs mt-1 truncate"
              style={{ color: 'var(--accent)' }}
            >
              {doc.source_url}
            </a>
          )}
        </div>
        <div
          className="flex items-center gap-1.5 badge-status flex-shrink-0"
          style={{
            background: doc.is_indexed ? 'rgba(34, 197, 94, 0.12)' : 'rgba(245, 158, 11, 0.12)',
            color: doc.is_indexed ? '#22c55e' : '#f59e0b',
          }}
        >
          {doc.is_indexed ? (
            <>
              <CheckCircle size={12} />
              Indexed
            </>
          ) : (
            <>
              <Clock size={12} />
              Indexing…
            </>
          )}
        </div>
      </div>
    </motion.div>
  )
}

function SearchResultCard({ result }: { result: SearchResult }) {
  return (
    <motion.div
      className="card-premium p-4"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <div className="flex items-start justify-between gap-3 mb-2">
        <h4 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
          {result.source_title}
        </h4>
        <div
          className="text-xs font-bold px-2 py-1 rounded flex-shrink-0"
          style={{
            background: `rgba(99, 102, 241, ${Math.min(result.score, 1) * 0.2})`,
            color: '#6366f1',
          }}
        >
          {(result.score * 100).toFixed(0)}%
        </div>
      </div>
      <p className="text-xs leading-relaxed" style={{ color: 'var(--text-muted)' }}>
        {result.chunk}
      </p>
      {result.source_url && (
        <a
          href={result.source_url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs mt-2 inline-block"
          style={{ color: 'var(--accent)' }}
        >
          View source →
        </a>
      )}
    </motion.div>
  )
}

export default function KnowledgePage() {
  const { data: docs, mutate: mutateDocs } = useSWR<KnowledgeDoc[]>(
    '/api/v1/knowledge',
    fetcher,
    { refreshInterval: 15000 }
  )

  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [searching, setSearching] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadTitle, setUploadTitle] = useState('')
  const [uploadContent, setUploadContent] = useState('')
  const [uploadUrl, setUploadUrl] = useState('')
  const [showUpload, setShowUpload] = useState(false)

  const handleSearch = async () => {
    if (!query.trim()) return
    setSearching(true)
    try {
      const res = (await knowledgeApi.search(query, 6)) as SearchResult[]
      setResults(res)
    } catch (_) {}
    finally {
      setSearching(false)
    }
  }

  const handleUpload = async () => {
    if (!uploadTitle || !uploadContent) return
    setUploading(true)
    try {
      await knowledgeApi.upload({
        title: uploadTitle,
        content: uploadContent,
        source_url: uploadUrl || undefined,
      })
      setUploadTitle('')
      setUploadContent('')
      setUploadUrl('')
      setShowUpload(false)
      mutateDocs()
    } catch (_) {}
    finally {
      setUploading(false)
    }
  }

  const indexedCount = docs?.filter((d) => d.is_indexed).length ?? 0

  return (
    <>
      <DashboardTopbar
        title="Knowledge Base"
        subtitle={`${indexedCount}/${docs?.length ?? 0} documents indexed for RAG onboarding`}
        actions={
          <button
            onClick={() => setShowUpload(!showUpload)}
            className="btn-premium flex items-center gap-2"
          >
            <Upload size={14} />
            Upload Doc
          </button>
        }
      />

      <div className="flex-1 p-6 max-w-4xl mx-auto w-full space-y-6">
        {/* Upload Form */}
        {showUpload && (
          <motion.div
            className="card-premium p-6"
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-label font-semibold" style={{ color: 'var(--text-primary)' }}>
                Add New Document
              </h3>
              <button
                onClick={() => setShowUpload(false)}
                className="p-1 rounded-lg transition-smooth"
                style={{
                  background: 'var(--bg-surface)',
                  color: 'var(--text-muted)',
                }}
              >
                <X size={16} />
              </button>
            </div>
            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>
                  Title
                </label>
                <input
                  className="input"
                  placeholder="e.g., AimHigherAI Docs - Introduction"
                  value={uploadTitle}
                  onChange={(e) => setUploadTitle(e.target.value)}
                />
              </div>
              <div>
                <label className="text-xs font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>
                  Source URL (optional)
                </label>
                <input
                  className="input"
                  placeholder="https://example.com/docs"
                  value={uploadUrl}
                  onChange={(e) => setUploadUrl(e.target.value)}
                />
              </div>
              <div>
                <label className="text-xs font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>
                  Content
                </label>
                <textarea
                  className="input font-mono text-xs"
                  rows={8}
                  placeholder="Paste document content here…"
                  value={uploadContent}
                  onChange={(e) => setUploadContent(e.target.value)}
                />
              </div>
              <div className="flex gap-2">
                <button
                  onClick={handleUpload}
                  disabled={uploading || !uploadTitle || !uploadContent}
                  className="btn-premium flex items-center gap-2"
                >
                  {uploading ? (
                    <>
                      <Loader2 size={14} className="animate-spin" />
                      Uploading…
                    </>
                  ) : (
                    <>
                      <Upload size={14} />
                      Upload & Index
                    </>
                  )}
                </button>
                <button
                  onClick={() => setShowUpload(false)}
                  className="btn-premium-ghost flex items-center gap-2"
                >
                  Cancel
                </button>
              </div>
            </div>
          </motion.div>
        )}

        {/* Search Section */}
        <motion.div className="card-premium p-6" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <h3 className="text-label font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>
            Semantic Search
          </h3>
          <div className="flex gap-2">
            <input
              className="input flex-1"
              placeholder="Search knowledge base…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            />
            <button
              onClick={handleSearch}
              disabled={searching || !query.trim()}
              className="btn-premium flex items-center gap-2 whitespace-nowrap"
            >
              {searching ? (
                <>
                  <Loader2 size={14} className="animate-spin" />
                  Searching…
                </>
              ) : (
                <>
                  <Search size={14} />
                  Search
                </>
              )}
            </button>
          </div>

          {/* Search Results */}
          {results.length > 0 && (
            <motion.div
              className="mt-4 space-y-3"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
            >
              {results.map((result, i) => (
                <SearchResultCard key={i} result={result} />
              ))}
            </motion.div>
          )}
        </motion.div>

        {/* Documents */}
        {docs && docs.length > 0 && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            <h3 className="text-label font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>
              Documents ({docs.length})
            </h3>
            <div className="space-y-2">
              {docs.map((doc) => (
                <DocumentCard key={doc.id} doc={doc} />
              ))}
            </div>
          </motion.div>
        )}

        {!docs || docs.length === 0 ? (
          <div
            className="flex flex-col items-center justify-center py-12 text-center"
            style={{ color: 'var(--text-muted)' }}
          >
            <Upload size={32} className="mb-3 opacity-30" />
            <p className="text-sm font-medium">No documents yet</p>
            <p className="text-xs mt-1">Upload knowledge documents to enable RAG-powered onboarding</p>
          </div>
        ) : null}
      </div>
    </>
  )
}
