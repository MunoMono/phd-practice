const joinClassNames = (...values) => values.filter(Boolean).join(' ')

const SectionHeading = ({
  title,
  description,
  className = ''
}) => {
  return (
    <div className={joinClassNames('section-heading', className)}>
      <h2 className="section-heading__title">{title}</h2>
      {description && <p className="section-heading__description">{description}</p>}
    </div>
  )
}

export default SectionHeading