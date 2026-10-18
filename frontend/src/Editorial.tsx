import { ArrowRight } from 'lucide-react'
import { GUIDE } from './seo'

export function HomeIntro() {
  return <section className="intro editorial-intro" aria-labelledby="page-title">
    <div className="intro-copy"><div className="eyebrow"><span className="status-dot"/> GEOMETRY × CERAMICS</div>
      <h1 id="page-title">Geometry, made tangible<span>.</span></h1>
      <p className="intro-lead">Mathematics describes remarkable forms. Clay gives us a way to hold them.</p>
      <p>I built Solids to explore how polyhedra take shape in slab clay. Choose a form, set its dimensions, and print reusable panels with edge-by-edge bevel settings. The geometry gives us a starting point; clay, joins and firing add their own tolerances.</p>
      <p className="byline">Built by <a href="https://tobiasbrownheft.xyz/">Tobias Brown-Heft</a> · Engineering, geometry &amp; ceramics.</p>
    </div>
    <a className="start-designing" href="#studio">Start designing <ArrowRight size={16}/></a>
  </section>
}

export function MethodSections() {
  return <div className="editorial-sections">
    <section id="method" className="method-section" aria-labelledby="method-title">
      <div className="eyebrow">FROM GEOMETRY TO CLAY</div><h2 id="method-title">How to use your slab templates</h2>
      <p className="section-intro">Independent polygon panels, made one at a time. Each reusable template tells you how many clay pieces to make and how to bevel their edges.</p>
      <ol className="method-steps">
        <li><h3>Choose a solid</h3><p>Explore 13 Archimedean and five Platonic solids, or try a recessed or outward-pyramid construction.</p></li>
        <li><h3>Set your clay dimensions</h3><p>Enter the desired fired base edge, working slab thickness and your clay’s measured linear shrinkage.</p></li>
        <li><h3>Print at 100%</h3><p>Download actual-size PDF or SVG panels. Disable Fit to Page and measure the calibration marks.</p></li>
        <li><h3>Cut, then bevel</h3><p>Keep the panel and edge IDs. Follow each edge’s angle and cut-side instruction; test a scrap joint first.</p></li>
        <li><h3>Assemble with care</h3><p>Match the panel edges and work with your clay’s joining needs. Allow for moisture, compression and drying.</p></li>
      </ol>
      <a className="editorial-link" href={GUIDE}>Read the complete slab-building method <ArrowRight size={15}/></a>
    </section>
    <section className="bevel-explainer" aria-labelledby="bevel-title">
      <div><div className="eyebrow">A SETTING, FROM THE SURFACE</div><h2 id="bevel-title">What are bevel angles?</h2></div>
      <div><p>A bevel removes a wedge from a panel’s edge so it can meet its neighbor. Solids calculates a symmetric tool setting from the interior dihedral—the angle between the assembled faces.</p>
        <p>The wire setting is measured <strong>from the clay surface</strong>: 90° is a square cut, normal to the slab; 0° is parallel. A 120° convex joint and a 240° reflex joint both use 60°, with different faces up.</p>
        <p>For convex panels, keep the <strong>exterior face down throughout cutting and beveling</strong>, with the interior up. Recessed constructions may need <strong>OUT / exterior-up</strong> bevels and extended blanks. Mixed panels need bevels from both sides.</p>
        <p>These are ideal geometric targets. Test the printed scale and a scrap joint before making a complete set.</p>
      </div>
    </section>
    <section id="faq" className="faq-section" aria-labelledby="faq-title"><div className="eyebrow">AT THE WORKBENCH</div><h2 id="faq-title">A few practical questions</h2>
      <details><summary>What comes in the download?</summary><p>One reusable copy of each unique panel type, with MAKE quantities and bevel labels inside the cutout. PDFs have calibration marks and tile large panels across sheets. Transformed designs also include cut-side labels and an edge-matching assembly reference.</p></details>
      <details><summary>How do thickness and shrinkage change the templates?</summary><p>Slab thickness is the roller setpoint in working clay. The base edge and apex offsets describe desired fired dimensions, enlarged once for your shrinkage estimate. Thickness changes the bevel offsets. Real shrinkage varies with clay, forming, drying and firing.</p></details>
      <details><summary>Can I make recessed or stellated forms?</summary><p>The designer supports selected face transformations and seven construction recipes. Recessed and outward-pyramid plans are experimental: surface checks and thick-panel overlap checks help reject invalid plans, but they do not simulate firing or guarantee assembly. Some multi-face corners need additional relief; overlapping panel solids block export.</p></details>
      <details><summary>Is Solids free, and do I need an account?</summary><p>Solids is free to use and needs no account. Save a project file to keep your dimensions and transformations. Your browser also remembers your last valid settings.</p></details>
    </section>
  </div>
}

function CutSection({ outside = false }: { outside?: boolean }) {
  const side=outside ? 'OUT' : 'IN'
  return <figure className="guide-figure"><svg viewBox="0 0 480 170" role="img" aria-label={`${side} bevel section: ${outside ? 'exterior' : 'interior'} face up, remove upper waste; ${outside ? 'the extended interior edge stays underneath' : 'preserve the exterior edge underneath'}.`}>
    <path d="M125 48H420V112H88Z" fill="#ddd7c7" stroke="#535d4b" strokeWidth="1.5"/>
    <path d="M88 48H125L88 112Z" fill="#d99b7840" stroke="#a75d3b" strokeDasharray="4 4"/>
    <path d="M88 112 125 48" stroke="#a75d3b" strokeWidth="2.5"/>
    <text x="160" y="29">{outside ? 'EXTERIOR' : 'INTERIOR'} FACE UP</text><text x="153" y="142">{outside ? 'INTERIOR' : 'EXTERIOR'} FACE DOWN</text>
    <text x="6" y="64">upper waste</text><path d="M63 71 99 71" stroke="#a75d3b"/>
  </svg><figcaption>{outside ? 'OUT: turn the extended blank over, then trim upper exterior waste back to the reference edge.' : 'IN: keep exterior down while cutting and beveling; the full exterior reference edge stays underneath.'}</figcaption></figure>
}

export function GuidePage() {
  return <>
    <a className="skip-link" href="#guide-content">Skip to the guide</a>
    <header className="masthead guide-masthead"><a href="/" className="wordmark" aria-label="Solids home">solids<span className="wordmark-dot">.</span></a><nav aria-label="Main navigation"><a href="/#studio">Design a solid</a><a href="/#method">How it works</a><a href="/#faq">FAQ</a></nav></header>
    <main id="guide-content" className="guide-page" tabIndex={-1}>
      <div className="eyebrow">THE SOLIDS METHOD / TOBIAS BROWN-HEFT</div><h1>Building polyhedra<br/>from slab clay<span>.</span></h1>
      <p className="guide-lead">A polyhedron starts as a set of flat faces. In clay, those faces become panels with thickness, beveled edges and joins. This guide connects the mathematical model to that practical work.</p>
      <a className="editorial-link" href="/#studio">Open the template designer <ArrowRight size={15}/></a>
      <nav className="guide-contents" aria-label="Guide contents"><a href="#panels">Panel templates</a><a href="#dimensions">Size &amp; shrinkage</a><a href="#angles">Bevel convention</a><a href="#cutting">Cutting sides</a><a href="#printing">Print scale</a><a href="#joining">Joining &amp; limits</a></nav>
      <section id="panels"><h2>Start with independent polygon panels</h2><p>Choose a solid and inspect its faces and joint settings in the designer. Solids includes all 13 Archimedean and five Platonic solids. Selected bases also support centered inward and outward pyramids, replacing a face with triangular panels.</p><p>The download contains one reusable copy of each unique panel type. A template marked MAKE 6 means six clay pieces from that pattern. Keep the template ID and edge labels when tracing. Templates are grouped by rotation, preserving bevel order and handedness; take care with chiral forms.</p><p>Construction names such as “excavated cube” and “outward-stellated dodecahedron” describe recipes. They do not imply a self-intersecting mathematical star polyhedron is a cuttable ceramic shell.</p></section>
      <section id="dimensions"><h2>Set fired size and working-clay thickness</h2><p><strong>Finished base edge</strong> means the desired original solid edge after firing. New triangular edges are calculated individually and may have unequal lengths. Apex depth or height is measured from the original face plane to its centered apex, also in fired millimeters.</p><p><strong>Slab thickness</strong> is the roller setpoint in working clay, before drying or firing. Enter a total linear shrinkage estimate measured for your clay and process. The working reference dimensions are the fired dimensions divided by <code>1 − shrinkage / 100</code>. Thickness is already a working dimension and is not enlarged again.</p><div className="guide-example"><h3>A cube as a scale check</h3><p>For a 120 mm fired edge and 10% linear shrinkage, the working exterior reference edge is 133.33 mm. With a 6 mm slab and 45° bevels, each interior edge is inset 6 mm, leaving a 121.33 mm interior square. This is a geometric calculation based on your shrinkage estimate, rather than a prediction of a particular firing.</p></div></section>
      <section id="angles"><h2>Measure the wire angle from the slab surface</h2><p>The interior dihedral is the angle inside the assembled shell between neighboring panels. A convex edge has an interior dihedral below 180°; a reflex, concave edge has one above 180°. A flat seam is 180°.</p><p>For a symmetric miter, the wire setting is <code>min(δ, 360° − δ) / 2</code>, where δ is the interior dihedral. A 90° setting is perpendicular to the slab, giving a square cut. A 0° setting is parallel to it. The setting is neither the full dihedral nor the angle from the normal.</p><div className="guide-table-wrap"><table><caption>Same setting, different cutting side</caption><thead><tr><th scope="col">Joint</th><th scope="col">Interior dihedral</th><th scope="col">Wire setting</th><th scope="col">Face up</th></tr></thead><tbody><tr><th scope="row">Convex</th><td>120°</td><td>60°</td><td>IN / interior</td></tr><tr><th scope="row">Reflex</th><td>240°</td><td>60°</td><td>OUT / exterior</td></tr><tr><th scope="row">Flat</th><td>180°</td><td>90°</td><td>Square cut</td></tr></tbody></table></div></section>
      <section id="cutting"><h2>Keep the reference edge, and follow the cut side</h2><p>For the original convex panels, explicitly keep the <strong>exterior face down throughout cutting and beveling</strong>. The interior faces up. Cut the full outline, then remove upper waste with the beveler in that same position. The full exterior footprint underneath is the dimensional reference.</p><CutSection/>
      <p>Concave constructions need a different blank. At a reflex edge the interior surface extends beyond the exterior reference, so Solids adds material to the raw outline. For an <strong>OUT</strong> bevel, turn the clay over with its exterior up and remove upper waste back to that reference. A panel with IN and OUT edges needs bevels from both sides; transfer its edge IDs before turning it.</p><CutSection outside/>
      <p>In transformed templates, the solid perimeter is the raw blank, the dash-dot contour is the final exterior reference, and the dashed contour is the final interior surface. Printed edge dimensions refer to the exterior reference. Those internal contours guide the bevel geometry; trace the solid blank outline for the initial cut.</p><p>For a 6 mm slab, the 60° test setting gives a 3.4641 mm inset at a 120° convex joint and a 3.4641 mm outward extension at a 240° reflex joint. Download the test coupons from a construction recipe and dry-fit both in scrap. Check that exterior reference edges meet and the inner edges close before making a full set.</p><p>The workflow is suited to adjustable wire tools that remove upper waste, such as the <a href="https://www.etsy.com/listing/4466016418/precision-beveler-pottery-bevel-cutter">Precision Beveler by KellyHoferStudios</a>. Check your own tool against the stated angle convention.</p></section>
      <section id="printing"><h2>Print at actual size and measure the marks</h2><p>Export PDF for US Letter, A4 or A3, or download an individual SVG in physical units. Print at <strong>100% / Actual Size</strong> with Fit to Page and borderless enlargement disabled. Measure the PDF’s 100 mm ruler and 1-inch square with a physical ruler before tracing.</p><p>Oversized panels tile with 10 mm overlap and registration crosses. Align matching crosses, join the complete outline and then trace it. The printed MAKE quantity stays inside the cutout. Transformed designs add assembly sheets mapping each joint to both panel instances and their template edge labels; parent IDs such as F001 remain in subface IDs such as F001.1.</p></section>
      <section id="joining"><h2>Test the joint before committing to the shell</h2><p>The calculated bevel is an ideal target. Moisture, roller variation, wire movement, compression, scoring, slip, joining and drying all change how a real panel behaves. Use your usual clay-joining practice and test representative joints at the working thickness.</p><p>Recessed and outward-pyramid fabrication plans are experimental. The app checks surface winding, closed manifold connectivity, degenerate faces and intersections. Transformed plans also check the finite-thickness mitered panel solids and block export when they overlap. Some high-valence corners, including cuboctahedron and rhombicuboctahedron corners, require additional corner relief that the app does not design.</p><p>Original convex exports retain their earlier behavior, so they do not certify every multi-face corner physically. No automatic assembly sequence, tool-access simulation, structural analysis or firing simulation is provided. A valid surface and a printable outline are useful starting points; a successful scrap dry-fit is the next check.</p></section>
      <div className="guide-return"><a className="start-designing" href="/#studio">Design your panels <ArrowRight size={16}/></a><a href="/#faq">More practical questions</a></div>
      <footer><span>solids. <span className="muted">Geometry, made tangible.</span></span><a href="https://tobiasbrownheft.xyz/">Tobias Brown-Heft</a></footer>
    </main>
  </>
}
