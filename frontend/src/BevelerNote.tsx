export function BevelerNote({ detailed = false }: { detailed?: boolean }) {
  return <p className="tool-note">Optimized for adjustable wire bevelers such as the <a href="https://www.etsy.com/listing/4466016418/precision-beveler-pottery-bevel-cutter" target="_blank" rel="noreferrer">{detailed ? 'Precision Beveler – Pottery Bevel Cutter – Custom Angle Beveler' : 'Precision Beveler'}</a> by KellyHoferStudios.</p>
}
