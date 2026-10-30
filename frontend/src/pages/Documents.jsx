import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../services/api.js'
import { EmptyState, ErrorMessage, PageHeader, Spinner } from '../components/ui.jsx'

const ALLOWED_EXTENSIONS = ['.pdf', '.docx', '.txt', '.md']
const MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024 // 20 MB

function formatBytes(bytes) {
  if (!bytes || bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

function formatDate(isoString) {
  if (!isoString) return '—'
  return new Date(isoString).toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}

const STATUS_CONFIG = {
  uploaded: {
    label: 'Uploaded',
    badge: 'bg-sky-500/15 text-sky-600 dark:text-sky-400 border-sky-500/30',
  },
  processing: {
    label: 'Processing',
    badge: 'bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30 animate-pulse',
  },
  processed: {
    label: 'Processed',
    badge: 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30',
  },
  failed: {
    label: 'Failed',
    badge: 'bg-rose-500/15 text-rose-600 dark:text-rose-400 border-rose-500/30',
  },
}

export default function Documents() {
  const navigate = useNavigate()
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Upload State
  const [dragActive, setDragActive] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(null)
  const [uploadError, setUploadError] = useState(null)
  const fileInputRef = useRef(null)

  // Details Modal State (Chunks preview)
  const [selectedDoc, setSelectedDoc] = useState(null)
  const [chunks, setChunks] = useState([])
  const [loadingChunks, setLoadingChunks] = useState(false)

  // Delete State
  const [deleteDoc, setDeleteDoc] = useState(null)
  const [deleting, setDeleting] = useState(false)

  // Search State
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState(null)
  const [searching, setSearching] = useState(false)

  const loadDocuments = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await api.listDocuments()
      setDocuments(data)
    } catch (err) {
      setError(err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadDocuments()
  }, [loadDocuments])

  // Auto-poll if any document is currently in "processing" or "uploaded" status
  useEffect(() => {
    const hasUnfinished = documents.some((d) => d.status === 'processing' || d.status === 'uploaded')
    if (!hasUnfinished) return

    const timer = setInterval(async () => {
      try {
        const fresh = await api.listDocuments()
        setDocuments(fresh)
      } catch {}
    }, 3000)

    return () => clearInterval(timer)
  }, [documents])

  function validateFile(file) {
    if (!file) throw new Error('No file selected')
    const ext = '.' + file.name.split('.').pop().toLowerCase()
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      throw new Error(`Unsupported format. Allowed: ${ALLOWED_EXTENSIONS.join(', ')}`)
    }
    if (file.size > MAX_FILE_SIZE_BYTES) {
      throw new Error('File exceeds the 20 MB size limit.')
    }
  }

  async function handleFileUpload(file) {
    setUploadError(null)
    try {
      validateFile(file)
    } catch (err) {
      setUploadError(err)
      return
    }

    setUploadProgress(0)
    try {
      await api.uploadDocument(file, {
        background: false, // process synchronously so user gets embeddings immediately
        onProgress: (pct) => setUploadProgress(pct),
      })
      setUploadProgress(100)
      setTimeout(() => setUploadProgress(null), 1000)
      await loadDocuments()
    } catch (err) {
      setUploadError(err)
      setUploadProgress(null)
    }
  }

  function onDragOver(e) {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(true)
  }

  function onDragLeave(e) {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
  }

  function onDrop(e) {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    const file = e.dataTransfer?.files?.[0]
    if (file) handleFileUpload(file)
  }

  async function openDocDetails(doc) {
    setSelectedDoc(doc)
    setChunks([])
    setLoadingChunks(true)
    try {
      const data = await api.getDocumentChunks(doc.id)
      setChunks(data)
    } catch (err) {
      setError(err)
    } finally {
      setLoadingChunks(false)
    }
  }

  async function confirmDelete() {
    if (!deleteDoc) return
    setDeleting(true)
    try {
      await api.deleteDocument(deleteDoc.id)
      setDeleteDoc(null)
      if (selectedDoc?.id === deleteDoc.id) setSelectedDoc(null)
      await loadDocuments()
    } catch (err) {
      setError(err)
    } finally {
      setDeleting(false)
    }
  }

  async function handleSearch(e) {
    e?.preventDefault()
    const q = searchQuery.trim()
    if (!q) {
      setSearchResults(null)
      return
    }
    setSearching(true)
    try {
      const res = await api.searchDocuments({ query: q, top_k: 6 })
      setSearchResults(res.results || [])
    } catch (err) {
      setError(err)
    } finally {
      setSearching(false)
    }
  }

  function askAboutDoc(doc) {
    navigate(`/chat?prompt=${encodeURIComponent(`What is the main topic of document "${doc.original_filename}"?`)}`)
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <PageHeader
        title="My Documents"
        subtitle="Upload and manage knowledge documents with AI semantic search and citations"
      >
        <button
          type="button"
          onClick={loadDocuments}
          className="btn-ghost px-3 py-2 text-xs font-semibold"
          title="Refresh document status"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          Refresh
        </button>
      </PageHeader>

      <ErrorMessage error={error} onRetry={loadDocuments} />
      <ErrorMessage error={uploadError} />

      {/* Drag & Drop Upload Zone */}
      <div
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        className={`relative rounded-2xl border-2 border-dashed p-8 text-center transition backdrop-blur-xs ${
          dragActive
            ? 'border-brand-500 bg-brand-500/10'
            : 'border-slate-300 dark:border-white/15 bg-white/40 dark:bg-slate-900/40 hover:border-brand-400'
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.txt,.md"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0]
            if (f) handleFileUpload(f)
            e.target.value = ''
          }}
        />

        <div className="mx-auto flex max-w-sm flex-col items-center justify-center">
          <div className="mb-3 rounded-2xl bg-brand-500/10 p-3 text-brand-600 dark:text-brand-300 shadow-inner">
            <svg className="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
              <path strokeLinecap="round" strokeLinejoin="round" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
          </div>
          <p className="font-semibold text-slate-800 dark:text-slate-100">
            Drag & drop document here, or{' '}
            <button
              id="browse-files-btn"
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="text-brand-600 dark:text-brand-400 hover:underline font-bold cursor-pointer"
            >
              browse
            </button>
          </p>
          <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
            Supports PDF, DOCX, TXT, and Markdown up to 20 MB
          </p>

          {/* Upload Progress Bar */}
          {uploadProgress !== null && (
            <div className="w-full mt-4">
              <div className="flex justify-between text-xs text-brand-600 dark:text-brand-300 font-semibold mb-1">
                <span>Uploading & embedding…</span>
                <span>{uploadProgress}%</span>
              </div>
              <div className="w-full bg-slate-200 dark:bg-white/10 h-2 rounded-full overflow-hidden">
                <div
                  className="bg-linear-to-r from-brand-500 to-cyan-500 h-full transition-all duration-200"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Semantic Search Bar */}
      <form onSubmit={handleSearch} className="flex gap-2 items-center">
        <div className="relative flex-1">
          <input
            type="text"
            className="input pr-8 py-2.5 text-sm"
            placeholder="Search within uploaded documents using AI semantic search…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => {
                setSearchQuery('')
                setSearchResults(null)
              }}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 text-xs"
            >
              ✕
            </button>
          )}
        </div>
        <button
          type="submit"
          className="btn-primary px-5 py-2.5 text-sm font-semibold cursor-pointer shrink-0"
          disabled={searching || !searchQuery.trim()}
        >
          {searching ? 'Searching…' : 'Search Passages'}
        </button>
      </form>

      {/* Search Results Display */}
      {searchResults !== null && (
        <div className="card border border-brand-500/30 p-5 space-y-3 animate-fade-in">
          <div className="flex items-center justify-between">
            <h3 className="font-bold text-sm text-slate-800 dark:text-slate-100 flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-brand-500 animate-ping" />
              Search Results for: &ldquo;{searchQuery}&rdquo; ({searchResults.length} passages found)
            </h3>
            <button
              type="button"
              onClick={() => setSearchResults(null)}
              className="text-xs text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
            >
              Close Results
            </button>
          </div>

          {searchResults.length === 0 ? (
            <p className="text-xs text-slate-500 dark:text-slate-400 py-3">
              No matching document passages found with sufficient similarity.
            </p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
              {searchResults.map((res, i) => (
                <div
                  key={i}
                  className="rounded-xl border border-slate-200 dark:border-white/10 p-3.5 bg-white/60 dark:bg-slate-900/60 text-xs space-y-1.5"
                >
                  <div className="flex items-center justify-between text-[11px] text-slate-400">
                    <span className="font-semibold text-brand-600 dark:text-brand-300 truncate">
                      {res.document_name}
                    </span>
                    <span>
                      {res.page_number ? `Page ${res.page_number}` : `Chunk #${res.chunk_index}`} ·{' '}
                      {(res.similarity_score * 100).toFixed(0)}% match
                    </span>
                  </div>
                  <p className="text-slate-700 dark:text-slate-300 line-clamp-3 leading-relaxed">
                    {res.content}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Document Listing */}
      {loading ? (
        <Spinner label="Loading documents…" />
      ) : documents.length === 0 ? (
        <EmptyState
          title="No documents uploaded yet"
          hint="Upload a PDF, DOCX, TXT, or Markdown document above to enable AI document analysis."
        />
      ) : (
        <div className="space-y-3">
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 px-1">
            Uploaded Files ({documents.length})
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {documents.map((doc) => {
              const statusCfg = STATUS_CONFIG[doc.status] || STATUS_CONFIG.uploaded
              return (
                <div
                  key={doc.id}
                  className="card flex flex-col justify-between hover:border-brand-500/40 transition group"
                >
                  <div>
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold border ${statusCfg.badge}`}
                      >
                        {statusCfg.label}
                      </span>
                      <span className="text-[11px] text-slate-400">
                        {formatBytes(doc.file_size_bytes)}
                      </span>
                    </div>

                    <h3 className="font-semibold text-sm text-slate-900 dark:text-slate-100 truncate mb-1">
                      {doc.original_filename}
                    </h3>

                    <div className="flex items-center gap-3 text-xs text-slate-400 mt-2">
                      <span>{doc.chunk_count || 0} chunks</span>
                      <span>·</span>
                      <span>{formatDate(doc.created_at)}</span>
                    </div>
                  </div>

                  <div className="mt-4 pt-3 border-t border-slate-100 dark:border-white/5 flex items-center justify-between gap-2">
                    <div className="flex items-center gap-1.5">
                      <button
                        type="button"
                        onClick={() => openDocDetails(doc)}
                        className="px-2.5 py-1 text-xs font-semibold rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-white/10 dark:hover:bg-white/15 text-slate-700 dark:text-slate-200 transition cursor-pointer"
                      >
                        Chunks
                      </button>
                      {doc.status === 'processed' && (
                        <button
                          type="button"
                          onClick={() => askAboutDoc(doc)}
                          className="px-2.5 py-1 text-xs font-semibold rounded-lg bg-brand-500/10 hover:bg-brand-500/20 text-brand-600 dark:text-brand-300 transition cursor-pointer"
                        >
                          Ask Chat
                        </button>
                      )}
                    </div>

                    <button
                      type="button"
                      onClick={() => setDeleteDoc(doc)}
                      className="p-1.5 text-slate-400 hover:text-rose-500 rounded-lg hover:bg-rose-500/10 transition cursor-pointer"
                      title="Delete document"
                    >
                      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Chunks & Details Modal */}
      {selectedDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs">
          <div className="card w-full max-w-2xl max-h-[85vh] flex flex-col shadow-2xl border border-slate-200 dark:border-white/10 p-6 animate-fade-in">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-white/10 shrink-0">
              <div>
                <h3 className="font-bold text-base text-slate-900 dark:text-slate-100 truncate">
                  {selectedDoc.original_filename}
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  {selectedDoc.chunk_count} chunk(s) · {formatBytes(selectedDoc.file_size_bytes)} · Status:{' '}
                  {selectedDoc.status}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedDoc(null)}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 p-1 rounded-lg"
              >
                ✕
              </button>
            </div>

            <div className="flex-1 overflow-y-auto py-4 space-y-3 min-h-0">
              {loadingChunks ? (
                <Spinner label="Loading document chunks…" />
              ) : chunks.length === 0 ? (
                <p className="text-center text-xs text-slate-400 py-6">
                  No text chunks available for this document.
                </p>
              ) : (
                chunks.map((c) => (
                  <div
                    key={c.id}
                    className="p-3.5 rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50/70 dark:bg-slate-900/50 text-xs space-y-1"
                  >
                    <div className="flex items-center justify-between text-[11px] text-slate-400 font-semibold">
                      <span>Chunk #{c.chunk_index + 1}</span>
                      <span>
                        {c.page_number ? `Page ${c.page_number}` : ''} ({c.token_count || c.char_count} chars)
                      </span>
                    </div>
                    <p className="text-slate-700 dark:text-slate-300 leading-relaxed font-mono text-[11px] whitespace-pre-wrap">
                      {c.content}
                    </p>
                  </div>
                ))
              )}
            </div>

            <div className="pt-3 border-t border-slate-200 dark:border-white/10 flex justify-end shrink-0">
              <button
                type="button"
                onClick={() => setSelectedDoc(null)}
                className="btn-primary px-4 py-2 text-xs font-semibold cursor-pointer"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs">
          <div className="card w-full max-w-md shadow-xl border border-slate-200 dark:border-white/10 p-6 animate-fade-in">
            <h3 className="text-base font-bold text-slate-900 dark:text-slate-100 mb-2">
              Delete Document?
            </h3>
            <p className="text-sm text-slate-500 dark:text-slate-400 mb-6">
              Delete &ldquo;{deleteDoc.original_filename}&rdquo; and all associated vector embeddings? This
              cannot be undone.
            </p>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setDeleteDoc(null)}
                className="btn-ghost px-4 py-2 text-sm"
                disabled={deleting}
              >
                Keep
              </button>
              <button
                id="confirm-delete-doc-btn"
                type="button"
                onClick={confirmDelete}
                className="btn bg-rose-600 hover:bg-rose-700 text-white px-4 py-2 text-sm font-semibold cursor-pointer"
                disabled={deleting}
              >
                {deleting ? 'Deleting…' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
