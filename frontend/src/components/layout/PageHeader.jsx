const joinClassNames = (...values) => values.filter(Boolean).join(' ')

const PageHeader = ({
  title,
  description,
  eyebrow,
  actions,
  className = ''
}) => {
  return (
    <header className={joinClassNames('page-header', className)}>
      <div className="page-header__content">
        {eyebrow && <p className="page-header__eyebrow">{eyebrow}</p>}
        <h1 className="page-header__title">{title}</h1>
        {description && <p className="page-header__description">{description}</p>}
      </div>

      {actions && <div className="page-header__actions">{actions}</div>}
    </header>
  )
}

export default PageHeader