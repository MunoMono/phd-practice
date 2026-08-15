import { Grid, Column } from '@carbon/react'

const joinClassNames = (...values) => values.filter(Boolean).join(' ')

export const PageGrid = ({ children, className = '' }) => {
  return (
    <Grid className={joinClassNames('page-grid', className)}>
      {children}
    </Grid>
  )
}

export const PageColumn = ({
  children,
  className = '',
  lg = 16,
  md = 8,
  sm = 4,
  xlg,
  max,
  ...rest
}) => {
  return (
    <Column
      lg={lg}
      md={md}
      sm={sm}
      xlg={xlg ?? 16}
      max={max ?? 16}
      className={joinClassNames('page-grid__column', className)}
      {...rest}
    >
      {children}
    </Column>
  )
}

export default PageGrid