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
import { useAsync, useMutation } from '@/lib/hooks'
import type { Service } from '@/types/api'

interface FormState {
  name: string
  description: string
  price: string
  category: string
  duration: string
  image: string
  is_active: boolean
  display_order: string
}

const BLANK: FormState = {
  name: '',
  description: '',
  price: '',
  category: '',
  duration: '',
  image: '',
  is_active: true,
  display_order: '0',
}

function toForm(service: Service | null): FormState {
  if (service === null) return BLANK
  return {
    name: service.name,
    description: service.description ?? '',
    price: service.price,
    category: service.category ?? '',
    duration: service.duration === null || service.duration === undefined ? '' : String(service.duration),
    image: service.image ?? '',
    is_active: service.is_active,
    display_order: String(service.display_order),
  }
}

function toPayload(form: FormState) {
  return {
    name: form.name.trim(),
    description: form.description.trim() || null,
    // Sent as a string; the backend parses it as a decimal and rejects a
    // non-numeric or negative value with a field-level message.
    price: form.price.trim(),
    category: form.category.trim() || null,
    duration: form.duration.trim() === '' ? null : Number(form.duration),
    image: form.image.trim() || null,
    is_active: form.is_active,
    display_order: Number(form.display_order || 0),
  }
}

export function ServicesPage() {
  const list = useAsync(() => api.services.list({ limit: 200 }), [])
  const [editing, setEditing] = useState<Service | null>(null)
  const [formOpen, setFormOpen] = useState(false)
  const [deleting, setDeleting] = useState<Service | null>(null)
  const action = useMutation()

  const openCreate = () => {
    setEditing(null)
    setFormOpen(true)
  }

  const openEdit = (service: Service) => {
    setEditing(service)
    setFormOpen(true)
  }

  const toggleActive = async (service: Service) => {
    await action.run(async () => {
      await api.services.setActive(service.id, !service.is_active)
      list.reload()
    })
  }

  const move = async (service: Service, direction: -1 | 1) => {
    const items = list.data?.items ?? []
    const index = items.findIndex((item) => item.id === service.id)
    const swap = items[index + direction]
    if (index < 0 || swap === undefined) return

    await action.run(async () => {
      await api.services.reorder({
        items: [
          { id: service.id, display_order: swap.display_order },
          { id: swap.id, display_order: service.display_order },
        ],
      })
      list.reload()
    })
  }

  const confirmDelete = async () => {
    if (deleting === null) return
    const ok = await action.run(async () => {
      await api.services.remove(deleting.id)
      list.reload()
    })
    if (ok) setDeleting(null)
  }

  return (
    <>
      <PageHeader
        title="Services"
        description="What your parlour offers, and in which order it appears."
        actions={
          <Button onClick={openCreate} disabled={action.busy}>
            Add service
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
          <Spinner label="Loading services" />
        ) : list.error !== null ? (
          <Banner tone="error">{list.error}</Banner>
        ) : (list.data?.items.length ?? 0) === 0 ? (
          <EmptyState
            title="No services yet"
            description="Add your first service to show it on the website."
            action={<Button onClick={openCreate}>Add service</Button>}
          />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Order</th>
                  <th>Service</th>
                  <th>Price</th>
                  <th>Category</th>
                  <th>Duration</th>
                  <th>Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {(list.data?.items ?? []).map((service, index, all) => (
                  <tr key={service.id}>
                    <td>
                      <div className="row" style={{ flexWrap: 'nowrap', gap: '2px' }}>
                        <Button
                          variant="ghost"
                          className="btn--small"
                          disabled={index === 0 || action.busy}
                          onClick={() => move(service, -1)}
                          aria-label={`Move ${service.name} up`}
                        >
                          ↑
                        </Button>
                        <Button
                          variant="ghost"
                          className="btn--small"
                          disabled={index === all.length - 1 || action.busy}
                          onClick={() => move(service, 1)}
                          aria-label={`Move ${service.name} down`}
                        >
                          ↓
                        </Button>
                        <span className="muted">{service.display_order}</span>
                      </div>
                    </td>
                    <td>
                      <div className="cell-title">{service.name}</div>
                      {service.description !== null && service.description !== undefined && (
                        <div className="cell-sub">
                          {service.description.length > 70
                            ? `${service.description.slice(0, 70)}…`
                            : service.description}
                        </div>
                      )}
                    </td>
                    <td>{service.price}</td>
                    <td>{service.category ?? '—'}</td>
                    <td>
                      {service.duration === null || service.duration === undefined
                        ? '—'
                        : `${service.duration} min`}
                    </td>
                    <td>
                      <Badge tone={service.is_active ? 'success' : 'neutral'}>
                        {service.is_active ? 'Active' : 'Hidden'}
                      </Badge>
                    </td>
                    <td className="actions">
                      <Button
                        variant="secondary"
                        className="btn--small"
                        onClick={() => openEdit(service)}
                      >
                        Edit
                      </Button>
                      <Button
                        variant="ghost"
                        className="btn--small"
                        onClick={() => toggleActive(service)}
                        disabled={action.busy}
                      >
                        {service.is_active ? 'Hide' : 'Show'}
                      </Button>
                      <Button
                        variant="ghost"
                        className="btn--small"
                        onClick={() => setDeleting(service)}
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

      {formOpen && (
        <ServiceForm
          service={editing}
          onClose={() => setFormOpen(false)}
          onSaved={() => {
            setFormOpen(false)
            list.reload()
          }}
        />
      )}

      {deleting !== null && (
        <ConfirmDialog
          title="Delete service"
          message={`Delete "${deleting.name}"? This cannot be undone.`}
          busy={action.busy}
          onCancel={() => setDeleting(null)}
          onConfirm={confirmDelete}
        />
      )}
    </>
  )
}

function ServiceForm({
  service,
  onClose,
  onSaved,
}: {
  service: Service | null
  onClose: () => void
  onSaved: () => void
}) {
  const [form, setForm] = useState<FormState>(() => toForm(service))
  const { busy, error, run } = useMutation()

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) =>
    setForm((current) => ({ ...current, [key]: value }))

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault()
    const payload = toPayload(form)
    const ok = await run(() =>
      service === null ? api.services.create(payload) : api.services.update(service.id, payload),
    )
    if (ok) onSaved()
  }

  return (
    <Modal
      title={service === null ? 'Add service' : `Edit ${service.name}`}
      onClose={onClose}
      wide
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button type="submit" form="service-form" busy={busy} disabled={busy}>
            {service === null ? 'Create' : 'Save changes'}
          </Button>
        </>
      }
    >
      <form id="service-form" onSubmit={onSubmit} className="stack">
        {error !== null && <Banner tone="error">{error}</Banner>}

        <Field label="Name">
          {(id) => (
            <TextInput
              id={id}
              value={form.name}
              onChange={(value) => set('name', value)}
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
          <Field label="Price" hint="A number, e.g. 45.00">
            {(id) => (
              <TextInput
                id={id}
                value={form.price}
                onChange={(value) => set('price', value)}
                required
                inputMode="decimal"
                placeholder="45.00"
              />
            )}
          </Field>

          <Field label="Duration" hint="In minutes">
            {(id) => (
              <TextInput
                id={id}
                type="number"
                min={0}
                value={form.duration}
                onChange={(value) => set('duration', value)}
              />
            )}
          </Field>

          <Field label="Category" hint="Free text, e.g. Hair, Skin, Nails">
            {(id) => (
              <TextInput
                id={id}
                value={form.category}
                onChange={(value) => set('category', value)}
              />
            )}
          </Field>

          <Field label="Display order" hint="Lower numbers appear first.">
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

        <Checkbox
          checked={form.is_active}
          onChange={(value) => set('is_active', value)}
          label="Visible on the public website"
        />
      </form>
    </Modal>
  )
}
