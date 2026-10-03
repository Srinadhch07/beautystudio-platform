import { useState } from 'react'
import type { FormEvent } from 'react'

import {
  Badge,
  Banner,
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  Field,
  Modal,
  PageHeader,
  Select,
  Spinner,
  TextArea,
  TextInput,
} from '@/components/ui'
import { api } from '@/lib/api'
import { formatDate } from '@/lib/format'
import { useAsync, useMutation } from '@/lib/hooks'
import type { Testimonial, TestimonialStatus } from '@/types/api'

const FILTERS: { value: TestimonialStatus | 'all'; label: string }[] = [
  { value: 'pending', label: 'Awaiting review' },
  { value: 'approved', label: 'Approved' },
  { value: 'rejected', label: 'Rejected' },
  { value: 'all', label: 'All' },
]

function Stars({ rating }: { rating: number }) {
  return (
    <span className="stars" aria-label={`${rating} out of 5`}>
      {'★'.repeat(rating)}
      <span style={{ color: 'var(--border-strong)' }}>{'★'.repeat(5 - rating)}</span>
    </span>
  )
}

export function TestimonialsPage() {
  const [filter, setFilter] = useState<TestimonialStatus | 'all'>('pending')
  const list = useAsync(
    () => api.testimonials.list({ limit: 200, ...(filter === 'all' ? {} : { status: filter }) }),
    [filter],
  )
  const [editing, setEditing] = useState<Testimonial | null>(null)
  const [deleting, setDeleting] = useState<Testimonial | null>(null)
  const action = useMutation()

  const moderate = async (item: Testimonial, status: TestimonialStatus, isVisible: boolean) => {
    await action.run(async () => {
      await api.testimonials.moderate(item.id, status, isVisible)
      list.reload()
    })
  }

  const confirmDelete = async () => {
    if (deleting === null) return
    const ok = await action.run(async () => {
      await api.testimonials.remove(deleting.id)
      list.reload()
    })
    if (ok) setDeleting(null)
  }

  return (
    <>
      <PageHeader
        title="Testimonials"
        description="A testimonial is only public once it is approved and visible."
        actions={
          <div style={{ minWidth: 190 }}>
            <Select value={filter} onChange={(value) => setFilter(value as TestimonialStatus | 'all')}>
              {FILTERS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          </div>
        }
      />

      {action.error !== null && (
        <Banner tone="error" onDismiss={action.clear}>
          {action.error}
        </Banner>
      )}

      <Card>
        {list.loading ? (
          <Spinner label="Loading testimonials" />
        ) : list.error !== null ? (
          <Banner tone="error">{list.error}</Banner>
        ) : (list.data?.items.length ?? 0) === 0 ? (
          <EmptyState
            title={filter === 'pending' ? 'Nothing awaiting review' : 'No testimonials'}
            description={
              filter === 'pending'
                ? 'New customer submissions will appear here for approval.'
                : 'Try a different filter.'
            }
          />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Customer</th>
                  <th>Review</th>
                  <th>Rating</th>
                  <th>Status</th>
                  <th>Received</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {(list.data?.items ?? []).map((item) => (
                  <tr key={item.id}>
                    <td>
                      <div className="cell-title">{item.customer_name}</div>
                    </td>
                    <td>
                      <p className="quote">{item.content}</p>
                    </td>
                    <td>
                      <Stars rating={item.rating} />
                    </td>
                    <td>
                      <div className="stack" style={{ gap: 4 }}>
                        <Badge
                          tone={
                            item.status === 'approved'
                              ? 'success'
                              : item.status === 'rejected'
                                ? 'danger'
                                : 'warning'
                          }
                        >
                          {item.status}
                        </Badge>
                        {!item.is_visible && <Badge tone="neutral">hidden</Badge>}
                      </div>
                    </td>
                    <td className="cell-sub">{formatDate(item.created_at)}</td>
                    <td className="actions">
                      {item.status !== 'approved' && (
                        <Button
                          className="btn--small"
                          onClick={() => moderate(item, 'approved', true)}
                          disabled={action.busy}
                        >
                          Approve
                        </Button>
                      )}
                      {item.status === 'approved' && !item.is_visible && (
                        <Button
                          className="btn--small"
                          onClick={() => moderate(item, 'approved', true)}
                          disabled={action.busy}
                        >
                          Show
                        </Button>
                      )}
                      {item.status !== 'rejected' && (
                        <Button
                          variant="secondary"
                          className="btn--small"
                          onClick={() => moderate(item, 'rejected', false)}
                          disabled={action.busy}
                        >
                          Reject
                        </Button>
                      )}
                      {item.is_visible && (
                        <Button
                          variant="ghost"
                          className="btn--small"
                          onClick={() => moderate(item, item.status, false)}
                          disabled={action.busy}
                        >
                          Hide
                        </Button>
                      )}
                      <Button
                        variant="ghost"
                        className="btn--small"
                        onClick={() => setEditing(item)}
                      >
                        Edit
                      </Button>
                      <Button
                        variant="ghost"
                        className="btn--small"
                        onClick={() => setDeleting(item)}
                      >
                        Delete
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {editing !== null && (
        <EditDialog
          item={editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null)
            list.reload()
          }}
        />
      )}

      {deleting !== null && (
        <ConfirmDialog
          title="Delete testimonial"
          message={`Delete the review from ${deleting.customer_name}? This cannot be undone.`}
          busy={action.busy}
          onCancel={() => setDeleting(null)}
          onConfirm={confirmDelete}
        />
      )}
    </>
  )
}

function EditDialog({
  item,
  onClose,
  onSaved,
}: {
  item: Testimonial
  onClose: () => void
  onSaved: () => void
}) {
  const [name, setName] = useState(item.customer_name)
  const [content, setContent] = useState(item.content)
  const [rating, setRating] = useState(String(item.rating))
  const { busy, error, run } = useMutation()

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault()
    // Deliberately does not send status or is_visible: editing copy must not
    // change the moderation state.
    const ok = await run(() =>
      api.testimonials.update(item.id, {
        customer_name: name.trim(),
        content: content.trim(),
        rating: Number(rating),
      }),
    )
    if (ok) onSaved()
  }

  return (
    <Modal
      title="Edit testimonial"
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button type="submit" form="testimonial-form" busy={busy} disabled={busy}>
            Save changes
          </Button>
        </>
      }
    >
      <form id="testimonial-form" onSubmit={onSubmit} className="stack">
        {error !== null && <Banner tone="error">{error}</Banner>}

        <Banner tone="info">
          Editing the wording does not change whether this review is published.
        </Banner>

        <Field label="Customer name">
          {(id) => (
            <TextInput
              id={id}
              value={name}
              onChange={setName}
              required
              maxLength={120}
            />
          )}
        </Field>

        <Field label="Review">
          {(id) => (
            <TextArea id={id} value={content} onChange={setContent} required />
          )}
        </Field>

        <Field label="Rating" hint="1 to 5.">
          {(id) => (
            <Select id={id} value={rating} onChange={setRating}>
              {[1, 2, 3, 4, 5].map((value) => (
                <option key={value} value={String(value)}>
                  {value}
                </option>
              ))}
            </Select>
          )}
        </Field>
      </form>
    </Modal>
  )
}
