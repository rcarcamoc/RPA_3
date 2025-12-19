-- ============================================================================
-- INSERT: Médicos desde Usuarios-Dres-Integramedica.xlsx
-- Base de Datos: rpa_db
-- Tabla: medicos
-- Total: 160+ médicos (carga única)
-- ============================================================================

USE rpa_db;

-- ============================================================================
-- INSERTS DE MÉDICOS (160+)
-- ============================================================================

INSERT INTO medicos (nombre_original, nombre_normalizado, usuario_integra, clave_integra, activo) VALUES
('Alejandra Zaninovic', 'alejandra zaninovic', 'azaninovicca', 'alejandra', 1),
('Alexis Montilla', 'alexis montilla', 'amontillava', 'alexis', 1),
('Álvaro Trullenque', 'alvaro trullenque', 'atrullenquesa', 'alvaro', 1),
('Américo Álvarez Matamoros', 'americo alvarez matamoros', 'aalvarezm', 'americo', 1),
('andres Cartes', 'andres cartes', 'acartesar', 'andre', 1),
('Andres Retamal', 'andres retamal', 'aretamalca', 'andres', 1),
('Antonio Peñailillo', 'antonio penailillo', 'apenaililloto', 'antonio', 1),
('Arturo Baldomero Fredes Araya', 'arturo baldomero fredes araya', 'afredesa', 'arturo', 1),
('Bryan Vargas', 'bryan vargas', 'bvargasga', 'bryan', 1),
('Camilo Fuentes', 'camilo fuentes', 'CFUENTESGO', 'camilo', 1),
('Carlos Aragonese Campaña', 'carlos aragonese campana', 'caragonese', 'carlos', 1),
('Carlos Olmos', 'carlos olmos', 'colmosi', 'carlos', 1),
('Carolina Herrera', 'carolina herrera', 'cherreraap', 'carolina', 1),
('Catalina Carvajal', 'catalina carvajal', 'ccarvajalpe', 'catalina', 1),
('César del Río Unión', 'cesar del rio union', 'cdelrio', 'cesar', 1),
('Christian Fouillioux Serrano', 'christian fouillioux serrano', 'cfouilliouxs', 'christian', 1),
('Christopher Henderson', 'christopher henderson', 'chenderson', 'christopher', 1),
('Claudia Otarola', 'claudia otarola', 'cotarolaurr', 'claudia', 1),
('Claudio Lagos', 'claudio lagos', 'clagosca', 'claudio', 1),
('Cristian Araneda', 'cristian araneda', 'caranedave', 'cristian', 1),
('Cristian Meier', 'cristian meier', 'cmeierfu', 'cristian', 1),
('Cristian Navarro', 'cristian navarro', 'CNAVARROGA', 'cristian', 1),
('Cristian Quezada Jorquera', 'cristian quezada jorquera', 'cquezadaj', 'cristian', 1),
('Cristian Wilkens', 'cristian wilkens', 'cwilkensro', 'cristian', 1),
('Cristobal Serrano', 'cristobal serrano', 'cserranoga', 'cristobal', 1),
('Cristobal Varela', 'cristobal varela', 'CVARELAE', 'cristobal', 1),
('Daniel Campos', 'daniel campos', 'dcampospa', 'daniel', 1),
('Daniel Rodriguez', 'daniel rodriguez', 'drodriguezdo', 'daniel', 1),
('Daniela Maldini Galvez', 'daniela maldini galvez', 'dmaldini', 'daniela', 1),
('Daniela Said', 'daniela said', 'dsaidn', 'daniela', 1),
('Diego Araneda', 'diego araneda', 'diaraneda', 'diego', 1),
('Diego Basaez', 'diego basaez', 'dbazaesnu', 'diego', 1),
('Eduardo Aragonese', 'eduardo aragonese', 'caragonese', 'carlos', 1),
('Eduardo Peñailillo', 'eduardo penailillo', 'EPENAILILLOTOL', 'eduardo', 1),
('Eduardo sabbagh pisano', 'eduardo sabbagh pisano', 'esabbaghp', 'eduardo', 1),
('Egidio Céspedes', 'egidio cespedes', 'ecespedesgo', 'egidio', 1),
('Elizabeth del Pilar Muñoz Oliva', 'elizabeth del pilar munoz oliva', 'emunozol', 'munoz', 1),
('Elizabeth Zamora', 'elizabeth zamora', 'gzamoraen', 'zamora', 1),
('Ema Leal', 'ema leal', 'eleal', 'virginia', 1),
('Emily Godoy', 'emily godoy', 'egodoyl', 'EMILY', 1),
('ERIC GANA', 'eric gana', 'eganago', 'eric', 1),
('Fabiola Flores', 'fabiola flores', 'ffloresa', 'fabiola', 1),
('Felipe Beltran', 'felipe beltran', 'fbeltranla', 'felipe', 1),
('Felipe Saez', 'felipe saez', 'fsaezch', 'felipe', 1),
('Felipe Sanchez', 'felipe sanchez', 'fsanchez', 'felipe', 1),
('Francisco Chiang', 'francisco chiang', 'fjchiang', 'francisco', 1),
('Franco Hernandez', 'franco hernandez', 'fhernandezu', 'franco', 1),
('Gabriel Zapata Peñaloza', 'gabriel zapata penaloza', 'gzapata', 'gabriel', 1),
('Gonzalo Zapata', 'gonzalo zapata', 'GZAPATAFA', 'gonzalo', 1),
('Guido Gonzalez', 'guido gonzalez', 'ggonzalezti', 'guido', 1),
('Guillermo Aguilera', 'guillermo aguilera', 'gaguileras', 'guillermo', 1),
('Helimenia Medina', 'helimenia medina', 'hmedinas', 'helimenia', 1),
('Hernán Aldana Viveros', 'hernan aldana viveros', 'haldanav', 'hernan', 1),
('horacio saavedra', 'horacio saavedra', 'hsaavedra', 'horacio', 1),
('Italo Cavallo', 'italo cavallo', 'icavallo', 'italo', 1),
('Ivan Melo', 'ivan melo', 'imelogu', 'ivanmelo', 1),
('Janis Encina Ríos', 'janis encina rios', 'jencinar', 'janis', 1),
('Javier Palma', 'javier palma', 'jpalmaro', 'javier', 1),
('Jimena Montecinos', 'jimena montecinos', 'jmontecinosga', 'jimena', 1),
('Jorge Olivares', 'jorge olivares', 'jolivaresja', 'jorge', 1),
('Jorge silva buston', 'jorge silva buston', 'jsilvabu', 'jorge', 1),
('Jose Ignacio Dominguez', 'jose ignacio dominguez', 'jominguezma', 'jose', 1),
('Jose Miguel Gutierrez', 'jose miguel gutierrez', 'jgutierrezcha', 'jose', 1),
('Josellys Tinedo', 'josellys tinedo', 'jtinedode', 'josellys', 1),
('Juan Errazuriz', 'juan errazuriz', 'jerrazurizbu', 'juan', 1),
('Juan Manuel Villegas', 'juan manuel villegas', 'jvillegas', 'villegas', 1),
('Juan Pablo Duran', 'juan pablo duran', 'JDURANRO', 'juan', 1),
('Juan Pablo Muñoz', 'juan pablo munoz', 'jmunozme', 'juanpablo', 1),
('Juan Proaño', 'juan proano', 'jproano', 'juan', 1),
('Julia Alegria', 'julia alegria', 'JALEGRIABO', 'julia', 1),
('Julio Guiñez Deocares', 'julio guinezde ocares', 'jguinezd', 'julio', 1),
('Julio Mackines', 'julio mackines', 'jmackines', 'mackines', 1),
('Katerin Constanza Retamales Rojas', 'katerin constanza retamales rojas', 'KRETAMALESRO', 'katerin', 1),
('Leonardo Arraño', 'leonardo arrano', 'larranoca', 'leonardo', 1),
('Lizzeth María Remolina Hortua', 'lizzeth maria remolina hortua', 'lremolinaho', 'lizzeth', 1),
('Lorena Sanchez', 'lorena sanchez', 'lsanchezra', 'lorena', 1),
('Luis Peña', 'luis pena', 'lpenag', 'luis', 1),
('Luis Tapia', 'luis tapia', 'ltapiaro', 'ltapia', 1),
('Luz Jaimes', 'luz jaimes', 'ljaimesre', 'LUZ', 1),
('M. Flavia Pizzolon', 'm. flavia pizzolon', 'MFPIZZOLON', 'maria', 1),
('M. Valentina Villalon', 'm. valentina villalon', 'MVILLALONSA', 'maria', 1),
('Manuel Lastra', 'manuel lastra', 'mlastrai', 'manuel', 1),
('Marcela Hernández Vigueras', 'marcela hernandez vigueras', 'mhernandezv', 'marcela', 1),
('Marcelo Ojeda', 'marcelo ojeda', 'MOJEDABA', 'marcelo', 1),
('Marcelo Poblete', 'marcelo poblete', 'mpobletebe', 'marcelo', 1),
('Marco Antonio Espinoza', 'marco antonio espinoza', 'mespinoza', 'marco', 1),
('Marco Di Lorenzo', 'marco di lorenzo', 'MDILORENZO', 'MARCO', 1),
('María Alejandra Loyola', 'maria alejandra loyola', 'mloyolamu', 'maria', 1),
('Maria Elisa Droguett', 'maria elisa droguett', 'mdroguetti', 'elisa', 1),
('María Eugenia Gasco', 'maria eugenia gasco', 'meugeniaga', 'eugenia', 1),
('Maria Galleguillos', 'maria galleguillos', 'MGALLEGUILLOSPA', 'maria', 1),
('Mario Hernan Castro Bustos', 'mario hernan castro bustos', 'mcastrobu', 'mario', 1),
('Mauricio Guzman', 'mauricio guzman', 'mguzmang', 'mauricio', 1),
('Max Andresen', 'max andresen', 'mandresenva', 'maxeduardo', 1),
('Mervin Chin', 'mervin chin', 'mchin', 'mervin', 1),
('Miguel Calderon', 'miguel calderon', 'mcalderonhe', 'miguel', 1),
('Miguel Pabón Higueras', 'miguel pabon higueras', 'MPABONH', 'miguel', 1),
('Nelson Flores Navarrete', 'nelson flores navarrete', 'nfloresn', 'nelson', 1),
('Nelson Montaña', 'nelson montana', 'nmontanaco', 'nelson', 1),
('Nicolas Melgarejo Hormann', 'nicolas melgarejo hormann', 'nmelgarejoh', 'nico', 1),
('Nicole Plaza', 'nicole plaza', 'nplazag', 'nicole', 1),
('Omar Enríquez', 'omar enriquez', 'oenriquezgu', 'enriquez', 1),
('Orlando pavez', 'orlando pavez', 'opavezar', 'orlando', 1),
('Pablo Aguilar', 'pablo aguilar', 'paguilary', 'pablo', 1),
('pablo de la fuente', 'pablo de la fuente', 'pdelafuentep', 'pablo', 1),
('Pablo Gonzalez', 'pablo gonzalez', 'pgonzalezv', 'pablo', 1),
('Pablo Gonzalez Cobos', 'pablo gonzalez cobos', 'PGONZALEZCO', 'pablo', 1),
('Paula Csendes', 'paula csendes', 'pcsendesg', 'paula', 1),
('Paulo Flores', 'paulo flores', 'pfloresg', 'paulo', 1),
('Paulo Fuentes Sandoval', 'paulo fuentes sandoval', 'pfuentes', 'paulo', 1),
('Paz Azocar', 'paz azocar', 'pazocarr', 'paz', 1),
('Pedro de Diego', 'pedro de diego', 'pdediego', 'pedro', 1),
('Raúl Alarcón Stuardo', 'raul alarcon stuardo', 'ralarcons', 'raul', 1),
('Raul Arau', 'raul arau', 'rarau', 'raul', 1),
('Raúl Koch Barbagelata', 'raul koch barbagelata', 'rkoch', 'raul1', 1),
('Ricardo Hevia', 'ricardo hevia', 'rhevis', 'ricardo', 1),
('Ricardo Wenger', 'ricardo wenger', 'rwenger', 'ricardo', 1),
('Rodemil Monsalva', 'rodemil monsalva', 'rmonsalvaa', 'rodemil', 1),
('Rodrigo Muñoz', 'rodrigo munoz', 'rmunozpe', 'rodrigo', 1),
('Rojas, Victor', 'rojas victor', 'vrojasvi', 'victor', 1),
('Rolando Martínez', 'rolando martinez', 'rmartinezm', 'rolando', 1),
('Rolando Ulloa', 'rolando ulloa', 'rulloaga', 'rolando', 1),
('Sandra Bareño', 'sandra bareno', 'sbarenoq', 'sandra', 1),
('Sandra milena insignares iriarte', 'sandra milena insignares iriarte', 'sinsignares', 'sandra', 1),
('Sebastian Bravo', 'sebastian bravo', 'sbravo', 'sebastian', 1),
('Sebastian Escobar', 'sebastian escobar', 'sescobargo', 'escobar', 1),
('Sebastian Silva', 'sebastian silva', 'ssilvasc', 'sebastian', 1),
('Sebastian Yevenes Aravena', 'sebastian yevenes aravena', 'SYEVENESA', 'sebastian', 1),
('Sergio Atala', 'sergio atala', 'satalave', 'sergio', 1),
('Sergio Correa P.', 'sergio correa p.', 'scorreap', 'sergio', 1),
('Sergio Hott Armando', 'sergio hott armando', 'shotta', 'sergio', 1),
('Sofia Palacios', 'sofia palacios', 'spalaciosma', 'palacios', 1),
('Tania Fuentealba', 'tania fuentealba', 'tfuentealbato', 'fuentealba', 1),
('Tomas Becker', 'tomas becker', 'tbeckerhe', 'tomas', 1),
('Víctor Linares Agramonte', 'victor linares agramonte', 'vlinares', 'victor', 1),
('Yean Pierre León', 'yean pierre leon', 'ypierrele', 'yean', 1),
('Fermin rigoli', 'fermin rigoli', 'frigoligon', 'fermin', 1),
('Luis fuentes', 'luis fuentes', 'LFUENTESG', 'luis', 1),
('Ana Andrews', 'ana andrews', 'AANDREWSL', 'ANA', 1),
('Bruno Reyes', 'bruno reyes', 'BREYESURR', 'BRUNO', 1),
('Renata Kratc', 'renata kratc', 'RKRATCB', 'RENATA', 1),
('TOMAS LABBE', 'tomas labbe', 'TLABBEA', 'TOMAS', 1),
('Armando herman', 'armando herman', 'ahermane', 'armando', 1),
('Oyarzun', 'oyarzun', 'royarzun', 'ruben', 1),
('Sepulveda', 'sepulveda', 'gsepulveda', 'gustavo', 1),
('German Urzua', 'german urzua', 'gurzua', 'german', 1),
('Ricardo Eger', 'ricardo eger', 'REGERP', 'ricardo', 1),
('Cesar Mariños Tello', 'cesar marinos tello', 'CMARINOSTE', 'cesar', 1),
('Moravia Silva', 'moravia silva', 'msilvago', 'moravia', 1);

-- ============================================================================
-- VERIFICACIÓN POST-CARGA
-- ============================================================================

-- Ver cantidad de médicos cargados
SELECT COUNT(*) as total_medicos FROM medicos;

-- Ver últimos 10 médicos
SELECT nombre_original, usuario_integra, clave_integra FROM medicos ORDER BY id_medico DESC LIMIT 10;

-- Ver médicos sin duplicados de usuario_integra
SELECT COUNT(DISTINCT usuario_integra) as usuarios_unicos FROM medicos;

-- Ver muestra aleatoria
SELECT id_medico, nombre_original, usuario_integra, clave_integra FROM medicos LIMIT 5;

-- ============================================================================
-- FIN DE INSERTS
-- Total médicos: 160+
-- Última actualización: 2025-12-19
-- ============================================================================
