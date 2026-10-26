import { USE_MOCK } from '../config'

export default function Card({ title, subtitle, children }) {
  return (
    <section className="card">
      <div className="card-head">
        <h2>{title}</h2>
        {USE_MOCK && <span className="badge-mock">Sample data</span>}
      </div>
      {subtitle && <p className="card-sub">{subtitle}</p>}
      {children}
    </section>
  )
}