const joinClassNames = (...values) => values.filter(Boolean).join(' ')

const PanelHeader = ({
  title,
  description,
  actions,
  className = '',
  titleAs = 'h3'
}) => {
  const TitleTag = titleAs

  return (
    <div className={joinClassNames('panel-header', className)}>
      <div className="panel-header__content">
        <TitleTag className="panel-header__title">{title}</TitleTag>
        {description && <p className="panel-header__description">{description}</p>}
      </div>

      {actions && <div className="panel-header__actions">{actions}</div>}
    </div>
  )
}

export default PanelHeader