import { useState } from 'react'
import type { FormEvent } from 'react'

import {
  Badge,
  Banner,
  Button,
  Card,
  Checkbox,
  ConfirmDialog,
  EmptyState,
  Field,
  Modal,
  PageHeader,
  Spinner,
  TextArea,
  TextInput,
} from '@/components/ui'
import { api } from '@/lib/api'
import { formatDate, fromDateTimeLocal, toDateTimeLocal } from '@/lib/format'
import { useAsync, useMutation } from '@/lib/hooks'
import type { Offer } from '@/types/api'

interface FormState {
  title: string
  description: string
  price: string
  original_price: string
  image: string
  valid_from: string
  valid_until: string
  is_active: boolean
  display_order: string
}

const BLANK: FormState = {
  title: '',
  description: '',
  price: '',
  original_price: '',
  image: '',
  valid_from: '',
  valid_until: '',
  is_active: true,
  display_order: '0',
}

function toForm(offer: Offer | null): FormState {
  if (offer === null) return BLANK
  return {
    title: offer.title,
    description: offer.description ?? '',
    price: offer.price,
    original_price: offer.original_price ?? '',
    image: offer.image ?? '',
    valid_from: toDateTimeLocal(offer.valid_from),
    valid_until: toDateTimeLocal(offer.valid_until),
    is_active: offer.is_active,
    display_order: String(offer.display_order),
  }
}

function toPayload(form: FormState) {
  return {
    title: form.title.trim(),
    description: form.description.trim() || null,
    price: form.price.trim(),
    original_price: form.original_price.trim() || null,
    image: form.image.trim() || null,
    valid_from: fromDateTimeLocal(form.valid_from),
    valid_until: fromDateTimeLocal(form.valid_until),
    is_active: form.is_active,
    display_order: Number(form.display_order || 0),
  }
}

/** Whether an offer is inside its window right now, which is what the public API serves. */
function validity(offer: Offer): 'current' | 'scheduled' | 'expired' | 'open' {
  const now = Date.now()
  const from = offer.valid_from ? new Date(offer.valid_from).getTime() : null
  const until = offer.valid_until ? new Date(offer.valid_until).getTime() : null
  if (from === null && until === null) return 'open'
  if (from !== null && from > now) return 'scheduled'
  if (until !== null && until < now) return 'expired'
  return 'current'
}

export function OffersPage() {
  const list = useAsync(() => api.offers.list({ limit: 200 }), [])
  const [editing, setEditing] = useState<Offer | null>(null)
  const [formOpen, setFormOpen] = useState(false)
  const [deleting, setDeleting] = useState<Offer | null>(null)
  const action = useMutation()

  const openCreate = () => {
    setEditing(null)
    setFormOpen(true)
  }

  const toggleActive = async (offer: Offer) => {
    await action.run(async () => {
      await api.offers.setActive(offer.id, !offer.is_active)
      list.reload()
    })
  }

  const move = async (offer: Offer, direction: -1 | 1) => {
    const items = list.data?.items ?? []
    const index = items.findIndex((item) => item.id === offer.id)
    const swap = items[index + direction]
    if (index < 0 || swap === undefined) return

    await action.run(async () => {
      await api.offers.reorder({
        items: [
          { id: offer.id, display_order: swap.display_order },
          { id: swap.id, display_order: offer.display_order },
        ],
      })
      list.reload()
    })
  }

  const confirmDelete = async () => {
    if (deleting === null) return
    const ok = await action.run(async () => {
      await api.offers.remove(deleting.id)
      list.reload()
    })
    if (ok) setDeleting(null)
  }

  return (
    <>
      <PageHeader
        title="Offers"
        description="Packages and promotions. An offer is shown publicly only while it is active and inside its validity window."
        actions={
          <Button onClick={openCreate} disabled={action.busy}>
            Add offer
          </Button>
        }
      />

      {action.error !== null && (
        <Banner tone="error" onDismiss={action.clear}>
          {action.error}
        </Banner>
      )}

      <Card>
        {list.loading ? (
          <Spinner label="Loading offers" />
        ) : list.error !== null ? (
          <Banner tone="error">{list.error}</Banner>
        ) : (list.data?.items.length ?? 0) === 0 ? (
          <EmptyState
            title="No offers yet"
            description="Add a package or promotion to feature it on the website."
            action={<Button onClick={openCreate}>Add offer</Button>}
          />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Order</th>
                  <th>Offer</th>
                  <th>Price</th>
                  <th>Valid</th>
                  <th>Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {(list.data?.items ?? []).map((offer, index, all) => {
                  const window = validity(offer)
                  return (
                    <tr key={offer.id}>
                      <td>
                        <div className="row" style={{ flexWrap: 'nowrap', gap: '2px' }}>
                          <Button
                            variant="ghost"
                            className="btn--small"
                            disabled={index === 0 || action.busy}
                            onClick={() => move(offer, -1)}
                            aria-label={`Move ${offer.title} up`}
                          >
                            ↑
                          </Button>
                          <Button
                            variant="ghost"
                            className="btn--small"
                            disabled={index === all.length - 1 || action.busy}
                            onClick={() => move(offer, 1)}
                            aria-label={`Move ${offer.title} down`}
                          >
                            ↓
                          </Button>
                        </div>
                      </td>
                      <td>
                        <div className="cell-title">{offer.title}</div>
                        {offer.original_price !== null &&
                          offer.original_price !== undefined &&
                          offer.original_price !== offer.price && (
                            <div className="cell-sub">
                              was {offer.original_price}
                            </div>
                          )}
                      </td>
                      <td>{offer.price}</td>
                      <td>
                        <div className="cell-sub">
                          {formatDate(offer.valid_from)} → {formatDate(offer.valid_until)}
                        </div>
                        <Badge
                          tone={
                            window === 'expired'
                              ? 'danger'
                              : window === 'scheduled'
                                ? 'warning'
                                : 'success'
                          }
                        >
                          {window === 'expired'
                            ? 'Expired'
                            : window === 'scheduled'
                              ? 'Scheduled'
                              : 'In window'}
                        </Badge>
                      </td>
                      <td>
                        <Badge tone={offer.is_active ? 'success' : 'neutral'}>
                          {offer.is_active ? 'Active' : 'Hidden'}
                        </Badge>
                      </td>
                      <td className="actions">
                        <Button
                          variant="secondary"
                          className="btn--small"
                          onClick={() => {
                            setEditing(offer)
                            setFormOpen(true)
                          }}
                        >
                          Edit
                        </Button>
                        <Button
                          variant="ghost"
                          className="btn--small"
                          onClick={() => toggleActive(offer)}
                          disabled={action.busy}
                        >
                          {offer.is_active ? 'Hide' : 'Show'}
                        </Button>
                        <Button
                          variant="ghost"
                          className="btn--small"
                          onClick={() => setDeleting(offer)}
                        >
                          Delete
                        </Button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {formOpen && (
        <OfferForm
          offer={editing}
          onClose={() => setFormOpen(false)}
          onSaved={() => {
            setFormOpen(false)
            list.reload()
          }}
        />
      )}

      {deleting !== null && (
        <ConfirmDialog
          title="Delete offer"
          message={`Delete "${deleting.title}"? This cannot be undone.`}
          busy={action.busy}
          onCancel={() => setDeleting(null)}
          onConfirm={confirmDelete}
        />
      )}
    </>
  )
}

function OfferForm({
  offer,
  onClose,
  onSaved,
}: {
  offer: Offer | null
  onClose: () => void
  onSaved: () => void
}) {
  const [form, setForm] = useState<FormState>(() => toForm(offer))
  const { busy, error, run } = useMutation()

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) =>
    setForm((current) => ({ ...current, [key]: value }))

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault()
    const payload = toPayload(form)
    const ok = await run(() =>
      offer === null ? api.offers.create(payload) : api.offers.update(offer.id, payload),
    )
    if (ok) onSaved()
  }

  return (
    <Modal
      title={offer === null ? 'Add offer' : `Edit ${offer.title}`}
      onClose={onClose}
      wide
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button type="submit" form="offer-form" busy={busy} disabled={busy}>
            {offer === null ? 'Create' : 'Save changes'}
          </Button>
        </>
      }
    >
      <form id="offer-form" onSubmit={onSubmit} className="stack">
        {error !== null && <Banner tone="error">{error}</Banner>}

        <Field label="Title">
          {(id) => (
            <TextInput
              id={id}
              value={form.title}
              onChange={(value) => set('title', value)}
              required
              maxLength={160}
            />
          )}
        </Field>

        <Field label="Description">
          {(id) => (
            <TextArea
              id={id}
              value={form.description}
              onChange={(value) => set('description', value)}
              maxLength={2000}
            />
          )}
        </Field>

        <div className="grid">
          <Field label="Price">
            {(id) => (
              <TextInput
                id={id}
                value={form.price}
                onChange={(value) => set('price', value)}
                required
                inputMode="decimal"
                placeholder="99.00"
              />
            )}
          </Field>

          <Field label="Original price" hint="Shown struck through. Optional.">
            {(id) => (
              <TextInput
                id={id}
                value={form.original_price}
                onChange={(value) => set('original_price', value)}
                inputMode="decimal"
                placeholder="149.00"
              />
            )}
          </Field>

          <Field label="Valid from" hint="Leave empty for no start date.">
            {(id) => (
              <TextInput
                id={id}
                type="datetime-local"
                value={form.valid_from}
                onChange={(value) => set('valid_from', value)}
              />
            )}
          </Field>

          <Field label="Valid until" hint="Leave empty for no end date.">
            {(id) => (
              <TextInput
                id={id}
                type="datetime-local"
                value={form.valid_until}
                onChange={(value) => set('valid_until', value)}
              />
            )}
          </Field>
        </div>

        <Field label="Image URL" hint="Upload from the Gallery page to get a URL.">
          {(id) => (
            <TextInput
              id={id}
              type="url"
              value={form.image}
              onChange={(value) => set('image', value)}
              placeholder="https://…"
            />
          )}
        </Field>

        <div className="grid">
          <Field label="Display order">
            {(id) => (
              <TextInput
                id={id}
                type="number"
                min={0}
                value={form.display_order}
                onChange={(value) => set('display_order', value)}
              />
            )}
          </Field>
          <div />
        </div>

        <Checkbox
          checked={form.is_active}
          onChange={(value) => set('is_active', value)}
          label="Active"
        />
      </form>
    </Modal>
  )
}
