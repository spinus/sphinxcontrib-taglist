# -*- coding: utf-8 -*-
import os
import re
from docutils.parsers.rst import roles, directives
from docutils import nodes, utils
from sphinx.environment import NoUri
from sphinx.locale import _
from sphinx.util.compat import Directive, make_admonition
from sphinx.util.osutil import copyfile


CSS_FILE = 'taglist.css'
CSS_FILE2 = 'taglist_tags.css'
ALL_TAGS_TAG='__all__'

def get_tags(s):
    return list(filter(lambda x:x,
               map(lambda x:x.strip(),
                   s.split(' ')
                  )
              )
       )



def status_role(name, rawtext, text, lineno, inliner, options=None, content=[]):
    status = utils.unescape(text.strip().replace(' ','_'))
    options = options or {}
    options.setdefault('classes', [])
    options['classes'] += ['taglist_tag', 'taglist_tag_%s'%status]
    node = nodes.emphasis(rawtext, status, **options)
    return [node], []


class tag_node(nodes.Admonition, nodes.Element): pass
class taglist(nodes.General, nodes.Element): 
    def __init__(self,*a,**b):
        super(taglist,self).__init__(*a,**b)
        self.tags = []


class TaglistDirective(Directive):
    has_content=True

    option_spec = {
        'tags': unicode,
    }

    def run(self):
        tl = taglist('')
        tl.tags = get_tags(self.options.get('tags',''))

        p = nodes.paragraph()
        text = nodes.paragraph()
        text += [nodes.Text("Tags:")]
        text += [nodes.Text(":tag:`%s`"%t) for t in tl.tags ]
        self.state.nested_parse(text,0,p)

        p += [tl]
        return [p]


class TagDirective(Directive):

    # this enables content in the directive
    has_content = True

    option_spec = {
        'tag': unicode,
    }

    def run(self):
        env = self.state.document.settings.env


        targetid = "taglist-%d" % env.new_serialno('taglist')
        targetnode = nodes.target('', '', ids=[targetid])

        status = self.options.get('tag', '')

        if not status and self.content and self.content[0]:
            x = self.content[0].strip()
            res=re.match(r'^\[(.*)\](.*)$',x)
            if res:
                status = res.group(1)
                self.content[0]=res.group(2).strip()

        taglist = get_tags(status)
        taglist_text = ' '.join([':tag:`%s`'% t for t in taglist])
        self.content[0] = taglist_text +' '+ self.content[0]

        ad = [ tag_node() ]
        tag = tag_node()
        tag.line = self.lineno
        tag.tags = taglist
        self.state.nested_parse(self.content,self.content_offset,tag)
        return [targetnode, tag]


def process_tags(app, doctree):
    # collect all tags in the environment
    # this is not done in the directive itself because it some transformations
    # must have already been run, e.g. substitutions
    env = app.builder.env
    if not hasattr(env, 'tags_all_tags'):
        env.tags_all_tags = []
    for node in doctree.traverse(tag_node):
        try:
            targetnode = node.parent[node.parent.index(node) - 1]
            if not isinstance(targetnode, nodes.target):
                raise IndexError
        except IndexError:
            targetnode = None
        env.tags_all_tags.append({
            'docname': env.docname,
            'lineno': node.line,
            'tagnode': node.deepcopy(),
            'tags': node.tags,
            'target': targetnode,
        })

def process_taglist_nodes(app, doctree, fromdocname):
    # Replace all taglist nodes with a list of the collected tags.
    # Augment each tag with a backlink to the original location.
    env = app.builder.env

    if not hasattr(env, 'tags_all_tags'):
        env.tags_all_tags = []

    for node in doctree.traverse(taglist):
        content = []

        #node_tags = get_tags(node.tags) 



        # TODO: group (and maybe even filter) by docname

        for tag_info in env.tags_all_tags:
            tags = tag_info['tags']
            if not set(tags).intersection(node.tags):
                continue

                    

            # (Recursively) resolve references in the tag content
            tag_entry = tag_info['tagnode']
            env.resolve_references(tag_entry, tag_info['docname'],
                                   app.builder)

            para = nodes.paragraph(classes=['tag-source'])
            # collect the first paragraph from the tag_node
            try:
                para.extend(tag_entry.children[0])
            except IndexError:
                para += nodes.Text(_('(empty spec)'))

            # Create a reference
            refnode = nodes.reference('', '', internal=True)
            innernode = nodes.emphasis(u'→', u'→')
            try:
                refnode['refuri'] = app.builder.get_relative_uri(
                    fromdocname, tag_info['docname'])
                refnode['refuri'] += '#' + tag_info['target']['refid']
            except NoUri:
                # ignore if no URI can be determined, e.g. for LaTeX output
                pass
            refnode.append(nodes.Text(' '))
            refnode.append(innernode)
            para += refnode

            content.append(para)

        node.replace_self(content)

def purge_tags(app, env, docname):
    if not hasattr(env, 'tags_all_tags'):
        return
    env.tags_all_tags = [tag for tag in env.tags_all_tags
                          if tag['docname'] != docname]

def visit_tag_node(self, node):
    self.visit_admonition(node)

def depart_tag_node(self, node):
    self.depart_admonition(node)

def add_stylesheet(app):
    app.add_stylesheet(CSS_FILE)
    app.add_stylesheet(CSS_FILE2)

def copy_stylesheet(app, exception):
    if app.builder.name != 'html' or exception:
        return
    app.info('Copying taglist stylesheet... ', nonl=True)
    dest = os.path.join(app.builder.outdir, '_static', CSS_FILE)
    dest2 = os.path.join(app.builder.outdir, '_static', CSS_FILE2)
    source = os.path.join(os.path.abspath(os.path.dirname(__file__)), CSS_FILE)
    copyfile(source, dest)

    f = open(dest2,'w')

    for tag, tag_dict in app.config.taglist_tags.items():
        f.write(".taglist_tag_%s {\n"%tag)
        for opt,val in tag_dict.items():
            f.write("%s: %s;\n"%(opt,val))
        f.write("}\n")

    f.close()
    app.info('done')

def setup(app):
    app.add_config_value('taglist_tags',{},'env')
    app.add_role('tag', status_role)
    app.add_node(taglist)
    app.add_node(tag_node,
                 html=(visit_tag_node, depart_tag_node),
                 latex=(visit_tag_node, depart_tag_node),
                 text=(visit_tag_node, depart_tag_node),
                 man=(visit_tag_node, depart_tag_node),
                 texinfo=(visit_tag_node, depart_tag_node))

    app.add_directive('tag', TagDirective)
    app.add_directive('taglist', TaglistDirective)
    app.connect('doctree-read', process_tags)
    app.connect('doctree-resolved', process_taglist_nodes)
    app.connect('env-purge-doc', purge_tags)
    app.connect('builder-inited', add_stylesheet)
    app.connect('build-finished', copy_stylesheet)
