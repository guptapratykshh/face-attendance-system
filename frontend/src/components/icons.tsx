import type { ReactNode, SVGProps } from 'react'

type IconProps = SVGProps<SVGSVGElement>

function Icon({ children, ...props }: IconProps & { children: ReactNode }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      {...props}
    >
      {children}
    </svg>
  )
}

export function IconToday(props: IconProps) {
  return (
    <Icon {...props}>
      <rect x="3.5" y="5" width="17" height="15.5" rx="2" />
      <path d="M8 3.5v3M16 3.5v3M3.5 10h17" />
    </Icon>
  )
}

export function IconPeople(props: IconProps) {
  return (
    <Icon {...props}>
      <circle cx="9" cy="8" r="3" />
      <path d="M3.5 19c.6-3.2 2.6-5 5.5-5s4.9 1.8 5.5 5" />
      <circle cx="17" cy="9" r="2.4" />
      <path d="M20.5 19c-.4-2.4-1.8-3.8-3.5-4.3" />
    </Icon>
  )
}

export function IconFace(props: IconProps) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="8.5" r="3.2" />
      <path d="M6 19.5c1.2-3.4 3.4-5 6-5s4.8 1.6 6 5" />
      <path d="M19 5.5l2 2-2 2M5 5.5L3 7.5l2 2" />
    </Icon>
  )
}

export function IconReports(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M5 19.5V9M10 19.5V5M15 19.5v-7M20 19.5v-4" />
    </Icon>
  )
}

export function IconKiosk(props: IconProps) {
  return (
    <Icon {...props}>
      <rect x="3.5" y="4" width="17" height="12" rx="1.8" />
      <path d="M8 20h8M12 16v4" />
    </Icon>
  )
}

export function IconActivity(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M3.5 12h4l2.5-6 4 12 2.5-6h4" />
    </Icon>
  )
}

export function IconLab(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M9 3.5v7L5 18.5h14L15 10.5v-7" />
      <path d="M8 3.5h8M8.5 13.5h7" />
    </Icon>
  )
}

export function IconCheckIn(props: IconProps) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M8.5 12.5l2.4 2.4 4.6-5.2" />
    </Icon>
  )
}

export function IconDays(props: IconProps) {
  return (
    <Icon {...props}>
      <rect x="3.5" y="5" width="17" height="15.5" rx="2" />
      <path d="M8 3.5v3M16 3.5v3M3.5 10h17M9 14.5l2 2 4-4" />
    </Icon>
  )
}

export function IconAccount(props: IconProps) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="8" r="3.2" />
      <path d="M5 19.5c1.3-3.6 3.6-5.3 7-5.3s5.7 1.7 7 5.3" />
    </Icon>
  )
}

export function IconSun(props: IconProps) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="12" r="3.4" />
      <path d="M12 3.5v2M12 18.5v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M3.5 12h2M18.5 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </Icon>
  )
}

export function IconMoon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M15.5 4.2A8.2 8.2 0 1 0 19.8 15 6.4 6.4 0 0 1 15.5 4.2z" />
    </Icon>
  )
}

export function IconSignOut(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M10 4.5H6.5A2 2 0 0 0 4.5 6.5v11A2 2 0 0 0 6.5 19.5H10" />
      <path d="M13.5 12H20M16.5 8.5L20 12l-3.5 3.5" />
    </Icon>
  )
}

export function IconStaff(props: IconProps) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="8" r="3" />
      <path d="M5 19c.8-3.4 3.2-5 7-5s6.2 1.6 7 5" />
      <path d="M17.5 6.5l1.5 1.5 3-3" />
    </Icon>
  )
}

export function IconOrgs(props: IconProps) {
  return (
    <Icon {...props}>
      <rect x="3.5" y="8" width="7" height="12.5" rx="1.4" />
      <path d="M10.5 12h10v8.5H10.5M6 11v.01M6 14.5v.01M6 18v.01M14.5 15.5v.01M18 15.5v.01" />
      <path d="M13 8V5.5h5L20.5 8" />
    </Icon>
  )
}

export function IconAssist(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M5 6.5h14a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H10l-4 3v-3H5a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2z" />
      <path d="M8 11h.01M12 11h.01M16 11h.01" />
    </Icon>
  )
}
