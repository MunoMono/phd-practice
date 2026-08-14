import { Button, InlineLoading, Tag, Tile } from '@carbon/react'
import { ArrowRight, Download } from '@carbon/icons-react'
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import PageHeader from '../../components/layout/PageHeader'
import { PageGrid, PageColumn as Column } from '../../components/layout/PageGrid'
import MarkdownRenderer from '../../components/MarkdownRenderer/MarkdownRenderer'
import { DOCUMENTATION_ENTRIES, getDocumentationEntry } from '../../data/documentationCatalog'
import './Documentation.scss'

const renderSectionBlock = (block) => {
  if (block.type === 'table') {
    return (
      <div key={block.caption || block.headers.join('-')} className="documentation-page__table-block">
        {block.caption ? <p className="documentation-page__table-caption">{block.caption}</p> : null}
        <div className="documentation-page__table-scroll">
          <table className="documentation-page__table">
            <thead>
              <tr>
                {block.headers.map((header) => (
                  <th key={header} scope="col">{header}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {block.rows.map((row) => (
                <tr key={row.join('-')}>
                  {row.map((cell) => (
                    <td key={cell}>{cell}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    )
  }

  return <p key={block.text}>{block.text}</p>
}

const Documentation = () => {
  const navigate = useNavigate()
  const { docId } = useParams()

  const selectedEntry = docId ? getDocumentationEntry(docId) : DOCUMENTATION_ENTRIES[0]
  const [markdownContent, setMarkdownContent] = useState('')
  const [markdownError, setMarkdownError] = useState('')
  const tableOfContents = selectedEntry?.sections || []

  useEffect(() => {
    if (!selectedEntry?.markdown) {
      setMarkdownContent('')
      setMarkdownError('')
      return undefined
    }

    const controller = new AbortController()

    fetch(selectedEntry.sourcePath, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Unable to load ${selectedEntry.sourceFormat}`)
        }
        return response.text()
      })
      .then((content) => {
        setMarkdownContent(content)
        setMarkdownError('')
      })
      .catch((error) => {
        if (error.name !== 'AbortError') {
          setMarkdownContent('')
          setMarkdownError(error.message)
        }
      })

    return () => controller.abort()
  }, [selectedEntry])

  const openEntry = (entry) => {
    navigate(`/documentation/${entry.slug}`)
  }

  return (
    <div className="documentation-page">
      <PageGrid>
        <Column>
          <PageHeader
            eyebrow="Documentation"
            title="Documentation"
            description="A report-style documentation reader for thesis texts, archival notes, and durable research memory."
            actions={(
              <div className="documentation-page__header-actions">
                <Tag type="blue" size="md">{selectedEntry?.markdown ? 'Markdown-backed' : 'Word-backed'}</Tag>
                <Tag type="cool-gray" size="md">Read only</Tag>
              </div>
            )}
          />
        </Column>

        <Column>
          <div className="documentation-page__reader-layout">
            <aside className="documentation-page__sidebar" aria-label="Documentation navigation">
              <Tile className="documentation-page__panel documentation-page__panel--intro">
                <p className="documentation-page__panel-eyebrow">Library</p>
                <h2 className="documentation-page__panel-title">Documentation catalogue</h2>
                <p className="documentation-page__panel-copy">
                  Durable thesis documents sourced from the local archive workspace.
                </p>
              </Tile>

              <Tile className="documentation-page__panel">
                <div className="documentation-page__panel-header">
                  <div>
                    <h2 className="documentation-page__panel-title">Documents</h2>
                    <p className="documentation-page__panel-copy">{DOCUMENTATION_ENTRIES.length} seeded item{DOCUMENTATION_ENTRIES.length === 1 ? '' : 's'}</p>
                  </div>
                </div>

                <div className="documentation-page__catalogue-list">
                  {DOCUMENTATION_ENTRIES.map((entry) => (
                    <button
                      key={entry.slug}
                      type="button"
                      className={`documentation-page__catalogue-item${selectedEntry?.slug === entry.slug ? ' documentation-page__catalogue-item--active' : ''}`}
                      onClick={() => openEntry(entry)}
                    >
                      <div className="documentation-page__catalogue-meta">
                        <span>{entry.id}</span>
                        <Tag type="green" size="sm">{entry.status}</Tag>
                      </div>
                      <strong>{entry.title}</strong>
                      <p>{entry.summary}</p>
                      <div className="documentation-page__catalogue-footer">
                        <span>{entry.sourceFormat}</span>
                        <span>{entry.markdown ? `Version ${entry.version} · ${entry.date}` : entry.date}</span>
                      </div>
                    </button>
                  ))}
                </div>
              </Tile>

              {selectedEntry ? (
                <>
                  <Tile className="documentation-page__panel">
                    <div className="documentation-page__panel-header">
                      <div>
                        <h2 className="documentation-page__panel-title">Metadata</h2>
                        <p className="documentation-page__panel-copy">Current document context</p>
                      </div>
                    </div>

                    <div className="documentation-page__metadata-grid">
                      <span>ID</span><strong>{selectedEntry.id}</strong>
                      <span>Author</span><strong>{selectedEntry.author}</strong>
                      <span>Status</span><strong>{selectedEntry.status}</strong>
                      <span>Classification</span><strong>{selectedEntry.classification}</strong>
                      <span>Source</span><strong>{selectedEntry.sourceFormat}</strong>
                      <span>Date</span><strong>{selectedEntry.date}</strong>
                      <span>{selectedEntry.markdown ? 'Version' : 'Words'}</span><strong>{selectedEntry.markdown ? '0.2' : selectedEntry.wordCount}</strong>
                      <span>Seed</span><strong>{selectedEntry.publishedLabel}</strong>
                    </div>

                    <div className="documentation-page__tag-row">
                      {selectedEntry.tags.map((tag) => (
                        <Tag key={tag} type="cool-gray" size="sm">{tag}</Tag>
                      ))}
                    </div>

                    <Button
                      as="a"
                      href={selectedEntry.sourcePath}
                      kind="tertiary"
                      renderIcon={Download}
                    >
                      Open source document
                    </Button>
                  </Tile>

                  <Tile className="documentation-page__panel">
                    <div className="documentation-page__panel-header">
                      <div>
                        <h2 className="documentation-page__panel-title">Contents</h2>
                        <p className="documentation-page__panel-copy">Auto-seeded reader outline</p>
                      </div>
                    </div>

                    <nav className="documentation-page__toc" aria-label="Document contents">
                      {tableOfContents.map((section) => (
                        <a key={section.id} href={`#${section.id}`} className="documentation-page__toc-link">
                          {section.heading}
                        </a>
                      ))}
                    </nav>
                  </Tile>
                </>
              ) : null}
            </aside>

            <div className="documentation-page__reader-stage">
              {selectedEntry ? (
                <article className="documentation-page__document">
                  <header className="documentation-page__document-header">
                    <p className="documentation-page__document-kicker">{selectedEntry.id}</p>
                    <h2 className="documentation-page__document-title">{selectedEntry.fullTitle}</h2>
                    {selectedEntry.markdown ? (
                      <div className="documentation-page__document-tags">
                        <Tag type="blue" size="md">Version {selectedEntry.version}</Tag>
                        <Tag type="cool-gray" size="md">{selectedEntry.date}</Tag>
                        <Tag type="green" size="md">{selectedEntry.status}</Tag>
                      </div>
                    ) : (
                      <p className="documentation-page__document-meta">
                        {selectedEntry.author} · {selectedEntry.documentLabel} · {selectedEntry.date} · {selectedEntry.wordCount} words
                      </p>
                    )}
                    <p className="documentation-page__document-summary">{selectedEntry.summary}</p>
                  </header>

                  {selectedEntry.markdown ? (
                    <section className="documentation-page__markdown-reader" aria-label="Technology Statement of Work">
                      {markdownError ? <p>{markdownError}</p> : null}
                      {!markdownContent && !markdownError ? <InlineLoading description="Loading canonical Markdown source" /> : null}
                      {markdownContent ? <MarkdownRenderer content={markdownContent} /> : null}
                    </section>
                  ) : null}

                  {selectedEntry.researchQuestions?.length ? (
                    <section className="documentation-page__question-block" aria-label="Research questions">
                      <h3>Research questions</h3>
                      {selectedEntry.researchQuestions.map((question) => (
                        <div key={question.label} className="documentation-page__question-item">
                          <span>{question.label}</span>
                          <p>{question.text}</p>
                        </div>
                      ))}
                    </section>
                  ) : null}

                  {!selectedEntry.markdown && selectedEntry.sections.map((section) => (
                    <section key={section.id} id={section.id} className="documentation-page__section">
                      <h3>{section.heading}</h3>
                      {(section.blocks || section.paragraphs.map((paragraph) => ({ type: 'paragraph', text: paragraph }))).map(renderSectionBlock)}
                    </section>
                  ))}
                </article>
              ) : (
                <Tile className="documentation-page__panel">
                  <div className="documentation-page__empty-state">
                    <h2>No documentation selected</h2>
                    <p>Choose a documentation entry from the catalogue to open the seeded reader.</p>
                  </div>
                </Tile>
              )}

              <div className="documentation-page__related-note">
                <span>Documentation continuity</span>
                <button type="button" className="documentation-page__related-link" onClick={() => openEntry(DOCUMENTATION_ENTRIES[0])}>
                  Return to the expanded abstract as the foundational documentation record
                  <ArrowRight size={16} />
                </button>
              </div>
            </div>
          </div>
        </Column>
      </PageGrid>
    </div>
  )
}

export default Documentation