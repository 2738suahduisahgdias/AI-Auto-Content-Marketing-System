import ts from 'typescript';
import {readFileSync} from 'node:fs';
const file=process.argv[2];const source=readFileSync(file,'utf8');
const tree=ts.createSourceFile(file,source,ts.ScriptTarget.ES2020,true,ts.ScriptKind.TSX);
const allowed=new Set(['AbsoluteFill','useCurrentFrame','useVideoConfig','interpolate','spring','Easing']);
const forbidden=new Set(['window','document','globalThis','global','process','fetch','XMLHttpRequest','WebSocket','Worker','eval','Function','require','navigator','location','localStorage','sessionStorage','indexedDB','constructor','prototype','__proto__','setTimeout','setInterval','requestAnimationFrame','Date','crypto','useEffect','useLayoutEffect','useState','dangerouslySetInnerHTML','innerHTML','createElement']);
const tags=new Set(['div','span','p','strong','b','em','section','h1','h2','h3','svg','g','path','rect','circle','line','polyline','polygon','ellipse','text','tspan','defs','linearGradient','stop','clipPath']);
const components=new Set(['React.Fragment']);
function declarations(n){if(ts.isFunctionDeclaration(n)&&n.name)components.add(n.name.text);if(ts.isVariableDeclaration(n)&&n.initializer&&(ts.isArrowFunction(n.initializer)||ts.isFunctionExpression(n.initializer)))components.add(n.name.getText(tree));ts.forEachChild(n,declarations)}
declarations(tree);
const errors=[];let exported=false;
function inspect(n){
 if(ts.isIdentifier(n)&&forbidden.has(n.text))errors.push('禁止使用 '+n.text);
 if(ts.isImportDeclaration(n)){
  if(!ts.isStringLiteral(n.moduleSpecifier)||!['react','remotion'].includes(n.moduleSpecifier.text))errors.push('只允许 react / remotion 导入');
  if(n.moduleSpecifier.text==='remotion'){
   const bindings=n.importClause?.namedBindings;
   if(!bindings||!ts.isNamedImports(bindings))errors.push('Remotion 必须使用具名导入');
   else for(const e of bindings.elements)if(!allowed.has((e.propertyName||e.name).text))errors.push('不支持的 Remotion API '+e.name.text);
  }
 }
 if(ts.isCallExpression(n)&&n.expression.kind===ts.SyntaxKind.ImportKeyword)errors.push('禁止动态导入');
 if(ts.isElementAccessExpression(n)&&(!n.argumentExpression||!ts.isNumericLiteral(n.argumentExpression)))errors.push('不允许动态下标访问');
 if(ts.isNewExpression(n)||ts.isWhileStatement(n)||ts.isDoStatement(n)||ts.isForStatement(n)||ts.isForInStatement(n)||ts.isForOfStatement(n))errors.push('禁止构造器与循环语句');
 if(ts.isPropertyAccessExpression(n)&&ts.isIdentifier(n.expression)&&n.expression.text==='Math'&&n.name.text==='random')errors.push('禁止随机数');
 if(ts.isJsxOpeningElement(n)||ts.isJsxSelfClosingElement(n)){const tag=n.tagName.getText(tree);if(!tags.has(tag)&&tag!=='AbsoluteFill'&&!components.has(tag))errors.push('不支持的 JSX 标签 '+tag)}
 if(ts.isJsxAttribute(n)&&(/^(on[A-Z]|src$|href$)/.test(n.name.getText(tree))))errors.push('禁止事件或外部资源属性');
 if((ts.isStringLiteral(n)||ts.isNoSubstitutionTemplateLiteral(n))&&/(https?:|data:|javascript:|url\s*\(|__proto__|constructor|prototype)/i.test(n.text))errors.push('禁止外部资源或原型访问');
 if(ts.isPropertyAssignment(n)&&['animation','transition'].includes(n.name.getText(tree).replace(/["']/g,'')))errors.push('动画必须使用 Remotion 帧，不可使用 CSS 动画');
 if((ts.isFunctionDeclaration(n)&&n.name?.text==='GeneratedScene'||ts.isVariableStatement(n)&&n.declarationList.declarations.some(d=>d.name.getText(tree)==='GeneratedScene'))&&n.modifiers?.some(m=>m.kind===ts.SyntaxKind.ExportKeyword))exported=true;
 ts.forEachChild(n,inspect);
}
inspect(tree);if(!exported)errors.push('缺少 export GeneratedScene');
const diagnostics=ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,target:ts.ScriptTarget.ES2020},reportDiagnostics:true,fileName:file}).diagnostics||[];
for(const d of diagnostics)if(d.category===ts.DiagnosticCategory.Error)errors.push(ts.flattenDiagnosticMessageText(d.messageText,' '));
if(errors.length){process.stderr.write([...new Set(errors)].join('\n'));process.exit(1)}
process.stdout.write(JSON.stringify({valid:true}));
