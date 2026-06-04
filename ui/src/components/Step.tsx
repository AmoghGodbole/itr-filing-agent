export default function Step({ n, title, active, done }: { n: number; title: string; active: boolean; done: boolean }) {
  return (
    <div className={`flex items-center gap-3 ${active ? 'text-blue-600 font-semibold' : done ? 'text-green-600' : 'text-gray-400'}`}>
      <div className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-bold
        ${active ? 'bg-blue-600 text-white' : done ? 'bg-green-500 text-white' : 'bg-gray-200'}`}>
        {done ? '✓' : n}
      </div>
      <span>{title}</span>
    </div>
  )
}
